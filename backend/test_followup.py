"""Follow-up question tests. Run: python -m pytest test_followup.py

The load-bearing test in this file is test_no_answer_can_ever_lower_a_grade.
Everything else is behaviour; that one is the safety property the whole design
rests on, and it is checked exhaustively rather than by example.
"""

import itertools

import pytest

import followup
import i18n
from followup import FOLLOW_UPS, MAX_QUESTIONS, apply, questions_for

LEVELS = ["unknown", "self_care", "urgent_care", "emergency"]


# --- which questions get asked -------------------------------------------

def test_questions_are_asked_for_a_matching_symptom():
    questions = questions_for(["headache"], "self_care")
    assert questions
    assert any(q["id"] == "headache_sudden" for q in questions)


def test_emergency_is_never_asked_anything():
    """Someone told to call an ambulance must not be handed a questionnaire.

    Nothing can raise an emergency grade, so every question would be delay
    bought for nothing.
    """
    assert questions_for(["headache", "fever"], "emergency") == []


def test_crisis_is_never_asked_anything():
    assert questions_for(["headache"], "crisis") == []


def test_nothing_recognised_means_nothing_to_ask():
    """A question triggered by no symptom would be a guess in clinical clothing."""
    assert questions_for([], "unknown") == []


def test_questions_are_capped():
    """Triage that turns into a form gets abandoned halfway."""
    # fever triggers several: rash, neck stiffness, breathlessness, fluids.
    questions = questions_for(["fever", "headache", "vomiting", "abdominal_pain"], "self_care")
    assert len(questions) <= MAX_QUESTIONS


def test_most_severe_questions_come_first():
    """When more apply than can be asked, the ones that matter most survive."""
    questions = questions_for(["headache", "fever", "abdominal_pain"], "self_care")
    ids = [q["id"] for q in questions]
    # The two red-flag questions outrank the appendicitis one.
    assert "headache_sudden" in ids
    assert "abdominal_right_lower" not in ids


def test_a_question_that_could_change_nothing_is_not_asked():
    """No point asking about neck stiffness that was already reported."""
    questions = questions_for(["headache", "neck_stiffness"], "urgent_care")
    assert all(q["id"] != "headache_neck" for q in questions)


def test_every_question_offers_all_three_answers():
    for question in questions_for(["headache"], "self_care"):
        assert [a["id"] for a in question["answers"]] == list(followup.ANSWER_IDS)


# --- what the answers do --------------------------------------------------

def test_yes_to_thunderclap_escalates_to_emergency():
    level, _, notes = apply("self_care", ["headache"], {"headache_sudden": "yes"})
    assert level == "emergency"
    assert "fu_note_headache_sudden" in notes


def test_yes_to_neck_stiffness_adds_the_symptom_and_the_rules_regrade():
    """The design point: reuse knowledge_graph.py rather than re-deciding here.

    headache + neck_stiffness is an existing curated meningitis rule, so adding
    the symptom is enough — this module states no urgency of its own.
    """
    level, symptoms, _ = apply("self_care", ["headache"], {"headache_neck": "yes"})
    assert "neck_stiffness" in symptoms
    assert level == "emergency"


def test_no_and_unsure_change_nothing():
    for answer in ("no", "unsure"):
        level, symptoms, notes = apply(
            "self_care", ["headache"], {"headache_sudden": answer}
        )
        assert level == "self_care", answer
        assert symptoms == ["headache"], answer
        assert notes == [], answer


def test_unknown_question_ids_are_ignored_not_rejected():
    """A client left open across a deploy must still get advice."""
    level, symptoms, _ = apply("self_care", ["headache"], {"no_such_question": "yes"})
    assert level == "self_care"
    assert symptoms == ["headache"]


def test_unknown_answer_values_are_ignored():
    level, _, _ = apply("self_care", ["headache"], {"headache_sudden": "maybe"})
    assert level == "self_care"


def test_no_answers_at_all_leaves_the_result_untouched():
    """Answering nothing is allowed: the first result was already a real one."""
    level, symptoms, notes = apply("urgent_care", ["fever"], {})
    assert (level, symptoms, notes) == ("urgent_care", ["fever"], [])


def test_several_answers_combine():
    level, symptoms, notes = apply(
        "self_care",
        ["fever", "headache"],
        {"headache_neck": "yes", "fluids_down": "yes"},
    )
    assert "neck_stiffness" in symptoms
    assert level == "emergency"
    assert len(notes) == 2


# --- the safety property --------------------------------------------------

@pytest.mark.parametrize("starting_level", LEVELS)
def test_no_answer_can_ever_lower_a_grade(starting_level):
    """Exhaustive: no combination of answers may de-escalate.

    This is what makes the questions safe to answer carelessly or wrongly, and
    it is the same guarantee context.py gives for age. Chest pain is graded
    emergency deliberately, over-triaging most people to avoid missing the few
    whose pain is cardiac; a "no" must never undo that. Checked across every
    question and every answer rather than by example, because a single new rule
    with a lowering effect would be easy to add and catastrophic to ship.
    """
    order = {level: index for index, level in enumerate(LEVELS)}
    symptoms = ["headache", "fever", "vomiting", "abdominal_pain", "cough"]

    question_ids = [question.id for question in FOLLOW_UPS]
    for answers in itertools.product(followup.ANSWER_IDS, repeat=len(question_ids)):
        combination = dict(zip(question_ids, answers))
        level, _, _ = apply(starting_level, symptoms, combination)
        assert order[level] >= order[starting_level], (starting_level, combination, level)


def test_added_symptoms_are_never_removed():
    """Re-grading must not drop what the patient actually reported."""
    _, symptoms, _ = apply(
        "self_care", ["headache", "fever"], {"headache_neck": "yes"}
    )
    assert {"headache", "fever"} <= set(symptoms)


# --- translation ----------------------------------------------------------

def _all_keys():
    keys = {f"fu_a_{answer_id}" for answer_id in followup.ANSWER_IDS}
    for question in FOLLOW_UPS:
        keys.add(f"fu_q_{question.id}")
        if question.note_key:
            keys.add(question.note_key)
    return keys


def test_every_question_and_note_is_translated():
    """A half-translated question is worse than none — it looks authoritative."""
    keys = _all_keys()

    missing_english = sorted(k for k in keys if k not in i18n.UI_EN)
    assert not missing_english, f"no English for: {missing_english}"

    failures = []
    for lang, table in (("hi", i18n.translations_hi), ("bn", i18n.translations_bn)):
        missing = sorted(k for k in keys if not table.UI.get(k))
        if missing:
            failures.append(f"{lang}: {missing}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("lang", ["hi", "bn"])
def test_translations_are_reachable_through_the_accessor(lang):
    """The table having a translation is not the same as the app finding it.

    The check above passed while every question still shipped in English,
    because the rendering path called the accessor for a different table and
    silently fell back. Nothing raised: a fully translated app served English.
    So this asserts on what a user would actually receive.
    """
    failures = []
    for key in sorted(_all_keys()):
        rendered = i18n.ui_string(key, lang)
        if rendered == i18n.UI_EN[key]:
            failures.append(key)
    assert not failures, f"{lang}: served English despite a translation: {failures}"


def test_added_symptoms_exist_in_the_vocabulary():
    """A follow-up that adds a symptom nobody defined would silently do nothing."""
    from symptoms import SYMPTOM_PHRASES

    unknown = sorted(
        {s for q in FOLLOW_UPS for s in q.adds} - set(SYMPTOM_PHRASES)
    )
    assert not unknown, f"follow-ups add unknown symptoms: {unknown}"


def test_escalation_targets_are_real_levels():
    bad = [q.id for q in FOLLOW_UPS if q.escalates_to and q.escalates_to not in LEVELS]
    assert not bad, f"follow-ups escalating to unknown levels: {bad}"
