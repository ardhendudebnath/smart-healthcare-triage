"""Age and duration rule tests. Run: python test_context.py"""

from context import (
    DURATIONS,
    MAX_PLAUSIBLE_AGE,
    apply,
    normalise_duration,
    options,
    parse_age,
)
from knowledge_graph import assess_urgency
from symptoms import ALL_IDS

# (symptoms, age, duration, level before, expected level after)
CASES = [
    # --- age ---------------------------------------------------------------
    # A fever in a baby is not the same illness as a fever in an adult.
    (["fever"], 0, None, "self_care", "emergency"),
    (["fever"], 30, None, "self_care", "self_care"),
    (["diarrhea", "vomiting"], 0, None, "urgent_care", "emergency"),
    # Under-fives dehydrate fast.
    (["diarrhea"], 3, None, "self_care", "urgent_care"),
    (["fever"], 4, None, "self_care", "urgent_care"),
    # Older adults deteriorate atypically.
    (["confusion"], 78, None, "urgent_care", "emergency"),
    (["fever"], 70, None, "self_care", "urgent_care"),
    # Working-age adults get no age modifier at all.
    (["fever"], 35, None, "self_care", "self_care"),
    (["joint_pain"], 70, None, "self_care", "self_care"),
    # --- duration ----------------------------------------------------------
    # The TB rule: three weeks of cough is the screening threshold in India.
    (["cough"], None, "weeks_over_3", "self_care", "urgent_care"),
    (["cough"], None, "days_1_3", "self_care", "self_care"),
    (["fever"], None, "days_4_7", "self_care", "urgent_care"),
    (["weight_loss"], None, "weeks_1_3", "urgent_care", "emergency"),
    (["headache"], None, "today", "self_care", "self_care"),
    # --- both together -----------------------------------------------------
    # Age and duration escalate one level between them, not one each.
    (["cough"], 70, "weeks_over_3", "self_care", "urgent_care"),
    (["fever"], 4, "days_4_7", "self_care", "urgent_care"),
    (["fever"], 70, "days_4_7", "self_care", "urgent_care"),
    # --- nothing recognised -------------------------------------------------
    # Age must not escalate a result the app never understood.
    ([], 80, "weeks_over_3", "unknown", "unknown"),
]


def test_rules():
    failures = []
    for symptoms, age, duration, before, expected in CASES:
        after, _ = apply(before, symptoms, age, duration)
        if after != expected:
            failures.append(
                f"{symptoms} age={age} duration={duration}: "
                f"{before} -> got {after}, expected {expected}"
            )
    assert not failures, "\n".join(failures)


def test_escalation_is_always_explained():
    """A level that changed must say what changed it."""
    failures = []
    for symptoms, age, duration, before, expected in CASES:
        after, notes = apply(before, symptoms, age, duration)
        if after != before and not notes:
            failures.append(f"{symptoms} age={age} duration={duration}: raised silently")
    assert not failures, "\n".join(failures)


def test_context_never_downgrades():
    """These rules may only raise urgency, never lower it.

    The whole design rests on this: because a wrong age can only make the app
    more cautious, the fields are safe to leave optional and safe to get wrong.
    """
    order = ["unknown", "self_care", "urgent_care", "emergency"]
    failures = []
    for symptom in ALL_IDS:
        base = assess_urgency([symptom])["level"]
        for age in (0, 3, 30, 70, 95):
            for duration in [None] + DURATIONS:
                after, _ = apply(base, [symptom], age, duration)
                if order.index(after) < order.index(base):
                    failures.append(
                        f"{symptom} age={age} duration={duration}: "
                        f"{base} downgraded to {after}"
                    )
    assert not failures, "\n".join(failures)


def test_context_escalates_at_most_one_level():
    """Age and duration together may raise the result by one step, never two.

    Both are modifiers of the same uncertainty, and compounding them turns
    ordinary childhood illness into an emergency-room referral. An app that
    shouts at everyone gets ignored by everyone, which costs exactly the people
    the shouting was meant to protect.

    The infant rule is the deliberate exception and is asserted separately.
    """
    order = ["unknown", "self_care", "urgent_care", "emergency"]
    failures = []
    for symptom in ALL_IDS:
        base = assess_urgency([symptom])["level"]
        for age in (2, 4, 30, 70, 90):
            for duration in DURATIONS:
                after, _ = apply(base, [symptom], age, duration)
                jump = order.index(after) - order.index(base)
                if jump > 1:
                    failures.append(
                        f"{symptom} age={age} duration={duration}: "
                        f"{base} -> {after} is a {jump}-level jump"
                    )
    assert not failures, "\n".join(failures)


def test_infant_rule_is_the_exception():
    """A baby under one with these symptoms goes straight to emergency."""
    level, notes = apply("self_care", ["fever"], 0, None)
    assert level == "emergency", level
    assert notes


def test_bad_input_is_ignored_not_trusted():
    """Nonsense in the optional fields must not drive a decision."""
    assert parse_age(None) is None
    assert parse_age("") is None
    assert parse_age("abc") is None
    assert parse_age(-5) is None
    assert parse_age(MAX_PLAUSIBLE_AGE + 1) is None
    # Real values still work, including strings from a form field.
    assert parse_age("34") == 34
    assert parse_age(0) == 0
    assert parse_age(65) == 65

    assert normalise_duration("weeks_over_3") == "weeks_over_3"
    assert normalise_duration("last tuesday") is None
    assert normalise_duration(None) is None


def test_bad_age_leaves_result_untouched():
    for bad in (None, "abc", -1, 500):
        after, notes = apply("self_care", ["fever"], parse_age(bad), None)
        assert after == "self_care", f"age={bad!r} changed the level"
        assert not notes, f"age={bad!r} produced {notes}"


def test_duration_options_are_ordered_and_labelled():
    listed = options()
    assert [o["id"] for o in listed] == DURATIONS
    assert all(o["label"] for o in listed)


if __name__ == "__main__":
    passed = failed = 0

    print("--- age and duration rules ---")
    for symptoms, age, duration, before, expected in CASES:
        after, notes = apply(before, symptoms, age, duration)
        ok = after == expected
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        detail = f"age={age} duration={duration}"
        print(f"{'PASS' if ok else 'FAIL'} | {symptoms} {detail}: {before} -> {after}")
        if not ok:
            print(f"       expected {expected}")
        elif notes:
            print(f"       {notes[0]}")

    print("\n--- invariants ---")
    for check in (
        test_escalation_is_always_explained,
        test_context_never_downgrades,
        test_context_escalates_at_most_one_level,
        test_infant_rule_is_the_exception,
        test_bad_input_is_ignored_not_trusted,
        test_bad_age_leaves_result_untouched,
        test_duration_options_are_ordered_and_labelled,
    ):
        try:
            check()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL | {check.__name__}\n       {exc}")
        else:
            passed += 1
            print(f"PASS | {check.__name__}")

    print(f"\n{passed} passed, {failed} failed")
