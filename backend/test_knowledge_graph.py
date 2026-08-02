"""Urgency rule tests. Run: python test_knowledge_graph.py"""

from knowledge_graph import (
    EMERGENCY_COMBOS,
    EMERGENCY_SINGLE,
    SCORE_THRESHOLD,
    URGENT_CARE_COMBOS,
    assess_urgency,
)
from symptoms import ALL_IDS, CONCERNING, weight_of

CASES = [
    # emergency — single red-flag symptoms (stroke signs)
    (["slurred_speech"], "emergency"),
    (["one_sided_weakness"], "emergency"),
    # emergency — combinations
    (["chest_pain", "difficulty_breathing"], "emergency"),
    (["chest_pain", "nausea"], "emergency"),
    (["headache", "neck_stiffness"], "emergency"),
    (["fever", "neck_stiffness"], "emergency"),
    (["confusion", "fever"], "emergency"),
    (["confusion", "headache"], "emergency"),
    # urgent care
    (["fever", "cough"], "urgent_care"),
    (["fever", "headache"], "urgent_care"),
    (["fever", "sore_throat"], "urgent_care"),
    (["abdominal_pain", "nausea"], "urgent_care"),
    (["diarrhea", "dizziness"], "urgent_care"),
    (["nausea", "dizziness"], "urgent_care"),
    # self care — real symptoms, no rule matched
    (["headache"], "self_care"),
    (["sore_throat"], "self_care"),
    (["fatigue"], "self_care"),
    (["cough", "dizziness"], "self_care"),
    # unknown
    ([], "unknown"),
    # severity ordering: an emergency inside a larger set must still win
    (["cough", "fatigue", "slurred_speech"], "emergency"),
    (["fever", "cough", "neck_stiffness"], "emergency"),
    # --- rules added with the expanded vocabulary -----------------------------
    # single red flags that stand alone
    (["chest_pain"], "emergency"),
    (["difficulty_breathing"], "emergency"),
    (["coughing_blood"], "emergency"),
    (["vomiting_blood"], "emergency"),
    (["allergic_reaction"], "emergency"),
    (["unable_to_urinate"], "emergency"),
    (["pregnancy_bleeding"], "emergency"),
    (["child_lethargy"], "emergency"),
    # new emergency combinations
    (["jaundice", "fever"], "emergency"),
    (["fainting", "palpitations"], "emergency"),
    (["numbness", "balance_problems"], "emergency"),
    (["fever", "rash"], "emergency"),
    (["confusion", "neck_stiffness"], "emergency"),
    # dengue-style presentation
    (["fever", "joint_pain"], "urgent_care"),
    (["fever", "muscle_pain"], "urgent_care"),
    # weight fallback: one CONCERNING symptom is enough for same-day care
    (["blood_in_stool"], "urgent_care"),
    (["jaundice"], "urgent_care"),
    (["confusion"], "urgent_care"),
    (["painful_urination"], "urgent_care"),
    (["difficulty_swallowing"], "urgent_care"),
    # weight fallback: enough ordinary symptoms stacked together
    (["cough", "dizziness", "headache"], "urgent_care"),
    # ordinary symptoms that must stay routine
    (["toothache"], "self_care"),
    (["blocked_nose"], "self_care"),
    (["itching"], "self_care"),
    (["low_mood", "insomnia"], "self_care"),
    (["joint_pain", "back_pain"], "self_care"),
]


def test_urgency():
    failures = []
    for symptoms, expected in CASES:
        got = assess_urgency(symptoms)["level"]
        if got != expected:
            failures.append(f"{symptoms} -> got {got!r}, expected {expected!r}")
    assert not failures, "\n".join(failures)


def test_rules_reference_real_symptoms():
    """No rule may name a symptom that does not exist.

    A typo in a rule fails silently -- the combination simply never fires -- so
    this is the difference between a rule that protects someone and a rule that
    only looks like it does.
    """
    known = set(ALL_IDS)
    failures = []
    for symptom in sorted(EMERGENCY_SINGLE - known):
        failures.append(f"EMERGENCY_SINGLE names unknown symptom {symptom!r}")
    for label, rules in (("EMERGENCY", EMERGENCY_COMBOS), ("URGENT", URGENT_CARE_COMBOS)):
        for combo, _, _ in rules:
            for symptom in sorted(combo - known):
                failures.append(f"{label} combo {sorted(combo)} names unknown {symptom!r}")
    assert not failures, "\n".join(failures)


def test_no_unreachable_rules():
    """Every curated rule must still be able to fire.

    The layers are checked in order, so a rule can be shadowed by an earlier one
    and become dead code. That is easy to introduce by accident: raising a
    symptom's weight to CONCERNING silently kills every urgent-care pair that
    mentions it, because the weight fallback would already have returned
    urgent_care. Dead rules are not merely untidy -- they make the rule table
    read as though it covers cases it no longer decides.
    """
    failures = []

    for combo, _, reason in EMERGENCY_COMBOS:
        shadowed = combo & EMERGENCY_SINGLE
        if shadowed:
            failures.append(
                f"emergency combo {sorted(combo)} can never fire: "
                f"{sorted(shadowed)} already emergency alone ({reason})"
            )

    for combo, _, reason in URGENT_CARE_COMBOS:
        shadowed = combo & EMERGENCY_SINGLE
        if shadowed:
            failures.append(
                f"urgent combo {sorted(combo)} can never fire: "
                f"{sorted(shadowed)} is emergency alone ({reason})"
            )
        heavy = sorted(s for s in combo if weight_of(s) >= CONCERNING)
        if heavy:
            failures.append(
                f"urgent combo {sorted(combo)} is redundant: {heavy} already "
                f"reaches urgent_care through the weight fallback ({reason})"
            )
        for emergency_combo, _, _ in EMERGENCY_COMBOS:
            if emergency_combo.issubset(combo):
                failures.append(
                    f"urgent combo {sorted(combo)} can never fire: it contains "
                    f"emergency combo {sorted(emergency_combo)}"
                )

    assert not failures, "\n".join(failures)


def test_every_symptom_produces_advice():
    """No symptom may grade as "unknown" on its own.

    "unknown" means the app could not understand the description at all. A
    symptom it definitely recognised must never produce that, or the user is told
    to rephrase something that was already understood perfectly.
    """
    failures = []
    for symptom in ALL_IDS:
        result = assess_urgency([symptom])
        if result["level"] == "unknown":
            failures.append(f"{symptom} alone graded as unknown")
    assert not failures, "\n".join(failures)


def test_reason_accompanies_every_escalation():
    """Anything above self_care must explain itself.

    Telling someone to go to an emergency room without saying why is the kind of
    output people ignore -- or panic at.
    """
    failures = []
    for symptoms, _ in CASES:
        result = assess_urgency(symptoms)
        if result["level"] in ("emergency", "urgent_care") and not result["reason"]:
            failures.append(f"{symptoms} -> {result['level']} with no reason")
    assert not failures, "\n".join(failures)


def test_score_threshold_is_reachable():
    """The weight fallback must be reachable with ordinary symptoms alone.

    If every symptom were CONCERNING or above, the sum-of-weights branch would be
    dead code and "several mild things at once" would never be caught.
    """
    ordinary = [s for s in ALL_IDS if 0 < weight_of(s) < CONCERNING]
    assert len(ordinary) >= SCORE_THRESHOLD, (
        f"only {len(ordinary)} symptoms are below CONCERNING — the "
        f"SCORE_THRESHOLD={SCORE_THRESHOLD} branch cannot be reached"
    )


if __name__ == "__main__":
    passed = failed = 0
    for symptoms, expected in CASES:
        got = assess_urgency(symptoms)["level"]
        ok = got == expected
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"{'PASS' if ok else 'FAIL'} | {symptoms} -> {got}")
        if not ok:
            print(f"       expected {expected}")

    print("\n--- rule table integrity ---")
    for check in (
        test_rules_reference_real_symptoms,
        test_no_unreachable_rules,
        test_every_symptom_produces_advice,
        test_reason_accompanies_every_escalation,
        test_score_threshold_is_reachable,
    ):
        try:
            check()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL | {check.__name__}\n{exc}")
        else:
            passed += 1
            print(f"PASS | {check.__name__}")

    print(f"\n{passed} passed, {failed} failed")
