"""Guards on the accuracy evaluation. Run: python -m pytest test_evaluation.py

The evaluation is a report, not a test: its job is to be read. These checks
exist so the report cannot quietly stop being true between readings — and, for
the held-out set, so it cannot quietly stop being held out.
"""

import contextlib
import io
import re

import main
import pytest
from eval_cases import CASES, LEVEL_ORDER
from eval_holdout import BASELINE, CATEGORIES, FINGERPRINT, HOLDOUT
from evaluation import (
    classify,
    evaluate,
    fingerprint,
    is_dangerous,
    report_holdout_sealed,
)

# Offline extraction, so a score never depends on a third-party API being up or
# on which model happened to answer.
main.extract_symptoms_llm = lambda text: None

VALID_LEVELS = set(LEVEL_ORDER) | {"crisis"}


@pytest.fixture(scope="module")
def development():
    return evaluate(CASES)


@pytest.fixture(scope="module")
def holdout():
    return evaluate(HOLDOUT)


def _normalise(text: str) -> str:
    """Case, punctuation and spacing removed, so a trivial reword still collides."""
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())


# --- development set ------------------------------------------------------

def test_no_dangerous_misses_in_development(development):
    """The development set is tuned against, so any dangerous miss here is one
    that was already known about and left in. That is never acceptable."""
    dangerous = [
        (case.id, case.expected, got)
        for case, got, _, danger in development["scored"]
        if danger
    ]
    assert not dangerous, f"dangerous misses in the development set: {dangerous}"


def test_development_accuracy_does_not_regress(development):
    """A floor to defend, not a target to celebrate. Raise it when it rises."""
    assert development["accuracy"] >= 0.88, f"{development['accuracy']:.1%} exact"


def test_over_triage_stays_bounded(development, holdout):
    """Caution is the design; indiscriminate escalation is not.

    An app that answered "emergency" to everything would have no dangerous misses
    and be useless, so the safe direction needs a limit too.
    """
    for name, verdict in (("development", development), ("held-out", holdout)):
        assert verdict["over_rate"] <= 0.20, f"{name}: {verdict['over_rate']:.1%} over-triaged"


def test_known_gaps_are_explained():
    """A recorded gap without a reason is just a failing case nobody removed."""
    thin = [c.id for c in CASES if c.expected_miss and len(c.why) < 40]
    assert not thin, f"known gaps needing a real explanation: {thin}"


def test_a_fixed_gap_is_noticed(development):
    """Graduate a gap once it passes, so the list stays honest."""
    fixed = [case.id for case, _, outcome, _ in development["known_gaps"] if outcome == "exact"]
    assert not fixed, (
        f"marked as known gaps but now pass: {fixed} — "
        "remove expected_miss so they count towards the score"
    )


# --- both sets --------------------------------------------------------------

def test_every_case_has_a_valid_expected_level():
    bad = [c.id for c in CASES + HOLDOUT if c.expected not in VALID_LEVELS]
    assert not bad, f"unknown expected level: {bad}"


def test_case_ids_are_unique_across_both_sets():
    """A shared id would let a report attribute one set's result to the other."""
    ids = [c.id for c in CASES + HOLDOUT]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicated, f"duplicate ids: {duplicated}"


# --- held-out set -----------------------------------------------------------

def test_holdout_fingerprint_is_unchanged():
    """Edits to held-out cases must be deliberate, never incidental.

    Changing a label so a case passes is the one way to make the held-out score
    rise without the app improving. This does not prevent it; it makes it take a
    second edit that stands out in review. If you are here because you added or
    replaced cases on purpose, follow the procedure in eval_holdout.py.
    """
    assert fingerprint(HOLDOUT) == FINGERPRINT, (
        "eval_holdout.py cases changed without FINGERPRINT being updated. "
        "If that was deliberate, see 'WHEN YOU DO NEED TO LOOK' in eval_holdout.py."
    )


def test_baseline_belongs_to_these_cases():
    """A baseline from a different set of cases compares two different things."""
    assert BASELINE is not None, "held-out BASELINE has not been recorded"
    assert BASELINE["fingerprint"] == FINGERPRINT, (
        "BASELINE was measured on different held-out cases; re-record it"
    )
    assert BASELINE["total"] == len(HOLDOUT)


def test_holdout_has_no_known_gaps():
    """Knowing a held-out case fails means it has been looked at, so it is not
    held out any more. Gaps belong in the development set."""
    marked = [c.id for c in HOLDOUT if c.expected_miss]
    assert not marked, f"held-out cases marked expected_miss: {marked}"


def test_holdout_categories_are_known_and_broad():
    """The sealed report names weak areas. An area with very few cases in it
    would effectively name the cases, and the report would stop being sealed."""
    unknown = sorted({c.category for c in HOLDOUT} - set(CATEGORIES))
    assert not unknown, f"undeclared categories: {unknown}"
    thin = {
        category: sum(1 for c in HOLDOUT if c.category == category)
        for category in CATEGORIES
    }
    too_small = {k: v for k, v in thin.items() if v < 4}
    assert not too_small, f"categories too small to stay anonymous: {too_small}"


def test_holdout_does_not_leak_into_development():
    """A case in both sets would be tuned against through the back door."""
    development = {_normalise(c.text) for c in CASES}
    leaked = [c.id for c in HOLDOUT if _normalise(c.text) in development]
    assert not leaked, f"held-out cases duplicated in the development set: {leaked}"


def test_holdout_does_not_regress(holdout):
    """Catches a development-side change that made unseen cases worse.

    That is what overfitting looks like from the outside: a phrase added to fix
    one case that quietly breaks others. Only aggregates are printed on failure,
    so finding out that something regressed does not reveal which case it was.
    """
    assert holdout["dangerous"] <= BASELINE["dangerous"], (
        f"held-out dangerous misses rose from {BASELINE['dangerous']} to "
        f"{holdout['dangerous']}. A recent change made unseen cases worse."
    )
    assert holdout["exact"] >= BASELINE["exact"], (
        f"held-out exact matches fell from {BASELINE['exact']} to {holdout['exact']}."
    )


def test_sealed_report_never_prints_a_case(holdout):
    """The whole point of sealing. If this fails, the default report has started
    leaking the held-out set to everyone who runs it."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        report_holdout_sealed(holdout)
    printed = buffer.getvalue()

    leaked = [c.id for c in HOLDOUT if c.text in printed or c.id in printed]
    assert not leaked, f"sealed report printed held-out cases: {leaked}"


# --- the metric -------------------------------------------------------------

def test_classify_directions():
    assert classify("emergency", "emergency") == "exact"
    assert classify("emergency", "self_care") == "under"
    assert classify("urgent_care", "unknown") == "under"
    assert classify("self_care", "emergency") == "over"
    assert classify("crisis", "emergency") == "missed_crisis"
    assert classify("crisis", "unknown") == "missed_crisis"
    assert classify("emergency", "crisis") == "wrong_pathway"
    # A minor complaint the app asked to have rephrased: a miss, not a danger.
    assert classify("self_care", "unknown") == "not_understood"


def test_what_counts_as_dangerous():
    assert is_dangerous("emergency", "urgent_care")
    assert is_dangerous("emergency", "unknown")
    assert is_dangerous("urgent_care", "self_care")
    assert is_dangerous("crisis", "unknown")
    assert is_dangerous("crisis", "emergency"), "a missed disclosure is dangerous whatever else it got"
    assert is_dangerous("emergency", "crisis"), "a counsellor instead of an ambulance"

    assert not is_dangerous("self_care", "unknown"), "asked to rephrase a cold"
    assert not is_dangerous("self_care", "emergency"), "over-cautious, not dangerous"
    assert not is_dangerous("unknown", "crisis"), "a counselling number shown unneeded"
    assert not is_dangerous("emergency", "emergency")
