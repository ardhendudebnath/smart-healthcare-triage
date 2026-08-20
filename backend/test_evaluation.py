"""Guards on the accuracy evaluation. Run: python -m pytest test_evaluation.py

The evaluation is a report, not a test: its job is to be read. These few checks
exist so the report cannot quietly stop being true between readings.
"""

import main
import pytest
from eval_cases import CASES, LEVEL_ORDER
from evaluation import classify, evaluate

# Offline extraction, so a score never depends on a third-party API being up or
# on which model happened to answer.
main.extract_symptoms_llm = lambda text: None


@pytest.fixture(scope="module")
def verdict():
    return evaluate()


def test_no_under_triage(verdict):
    """The one that matters.

    Under-triage means the app told someone their problem was less urgent than
    it is. knowledge_graph.py promises the opposite -- "when in doubt,
    escalate" -- and this is the only check that holds the code to it.

    It was 26.8% the first time it was run, including a textbook heart attack
    and a FAST-positive stroke, both scoring as nothing recognised. The unit
    tests were all green throughout, because they phrase their inputs the way
    the vocabulary spells them.
    """
    under = [
        (case.id, case.expected, got)
        for case, got, outcome in verdict["live"]
        if outcome == "under"
    ]
    assert not under, f"graded below the expected urgency: {under}"


def test_accuracy_does_not_regress(verdict):
    """A floor to defend, not a target to celebrate.

    Set just below the measured figure so ordinary variation does not trip it,
    while a real regression does. Raise it when the score rises.
    """
    assert verdict["accuracy"] >= 0.88, f"{verdict['accuracy']:.1%} exact match"


def test_over_triage_stays_bounded(verdict):
    """Caution is the design; indiscriminate escalation is not.

    An app that answered "emergency" to everything would score zero
    under-triage and be useless, so the safe direction needs a limit too.
    """
    assert verdict["over_triage_rate"] <= 0.20, f"{verdict['over_triage_rate']:.1%} over-triaged"


def test_every_case_has_a_valid_expected_level():
    valid = set(LEVEL_ORDER) | {"crisis"}
    bad = [c.id for c in CASES if c.expected not in valid]
    assert not bad, f"cases with an unknown expected level: {bad}"


def test_case_ids_are_unique():
    """Duplicated ids would silently overwrite each other in any report."""
    seen = [c.id for c in CASES]
    assert len(seen) == len(set(seen)), "duplicate case ids"


def test_known_gaps_are_explained():
    """A recorded gap without a reason is just a failing case nobody removed."""
    thin = [c.id for c in CASES if c.expected_miss and len(c.why) < 40]
    assert not thin, f"known gaps needing a real explanation: {thin}"


def test_a_fixed_gap_is_noticed(verdict):
    """Graduate a gap once it passes, so the list stays honest.

    Left alone, expected_miss becomes a place cases go to be forgotten, and the
    scored set slowly stops covering the things that were hardest.
    """
    fixed = [case.id for case, _, outcome in verdict["known_gaps"] if outcome == "exact"]
    assert not fixed, (
        f"these are marked as known gaps but now pass: {fixed} — "
        "remove expected_miss so they count towards the score"
    )


def test_classify_directions():
    assert classify("emergency", "emergency") == "exact"
    assert classify("emergency", "self_care") == "under"
    assert classify("self_care", "emergency") == "over"
    # Crisis is a separate pathway, not a rung on the ladder, so confusing it
    # with an urgency grade is neither under nor over.
    assert classify("crisis", "emergency") == "wrong_pathway"
    assert classify("emergency", "crisis") == "wrong_pathway"
