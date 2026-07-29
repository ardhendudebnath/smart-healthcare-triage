"""Safety override tests. Run: python test_safety.py"""

from safety import (
    check_crisis,
    check_emergency_override,
    escalate,
    has_severity_marker,
)

# Descriptions of real emergencies that use NO word from the 16-symptom
# vocabulary. Without the override these all grade as "unknown".
EMERGENCY_CASES = [
    "my father collapsed and is not responding",
    "he is unconscious",
    "she passed out and wont wake up",
    "the baby is not breathing",
    "I think he is having a heart attack",
    "my mother is having a seizure",
    "the wound wont stop bleeding",
    "he took too many pills",
    "she is choking",
    "grandpa is turning blue",
]

NOT_EMERGENCY_CASES = [
    "I have a mild headache",
    "sore throat since yesterday",
    "feeling a bit tired",
    "I want to book an appointment",
]

CRISIS_CASES = [
    "I want to die",
    "I have been thinking about suicide",
    "I want to hurt myself",
    "thinking of ending my life",
]

NOT_CRISIS_CASES = [
    "my head is killing me",
    "this cough is killing me",
    "I have a fever",
]

SEVERITY_CASES = [
    "the worst headache of my life",
    "severe stomach pain",
    "unbearable pain in my chest",
    "excruciating back pain",
]

NOT_SEVERITY_CASES = [
    "mild headache",
    "slight fever",
    "a bit of a cough",
]


def test_emergency_override():
    failures = []
    for text in EMERGENCY_CASES:
        if check_emergency_override(text) is None:
            failures.append(f"MISSED emergency: {text!r}")
    for text in NOT_EMERGENCY_CASES:
        got = check_emergency_override(text)
        if got is not None:
            failures.append(f"FALSE emergency ({got}): {text!r}")
    assert not failures, "\n".join(failures)


def test_crisis():
    failures = []
    for text in CRISIS_CASES:
        if not check_crisis(text):
            failures.append(f"MISSED crisis: {text!r}")
    for text in NOT_CRISIS_CASES:
        if check_crisis(text):
            failures.append(f"FALSE crisis: {text!r}")
    assert not failures, "\n".join(failures)


def test_severity():
    failures = []
    for text in SEVERITY_CASES:
        if not has_severity_marker(text):
            failures.append(f"MISSED severity: {text!r}")
    for text in NOT_SEVERITY_CASES:
        if has_severity_marker(text):
            failures.append(f"FALSE severity: {text!r}")
    assert not failures, "\n".join(failures)


def test_escalate():
    assert escalate("unknown") == "self_care"
    assert escalate("self_care") == "urgent_care"
    assert escalate("urgent_care") == "emergency"
    # Emergency is the top — must not wrap around or overflow.
    assert escalate("emergency") == "emergency"
    assert escalate("nonsense") == "nonsense"


if __name__ == "__main__":
    passed = failed = 0

    checks = [
        ("emergency override", EMERGENCY_CASES, lambda t: check_emergency_override(t) is not None, True),
        ("not emergency", NOT_EMERGENCY_CASES, lambda t: check_emergency_override(t) is not None, False),
        ("crisis", CRISIS_CASES, check_crisis, True),
        ("not crisis", NOT_CRISIS_CASES, check_crisis, False),
        ("severity", SEVERITY_CASES, has_severity_marker, True),
        ("not severity", NOT_SEVERITY_CASES, has_severity_marker, False),
    ]

    for label, cases, fn, expected in checks:
        print(f"--- {label} ---")
        for text in cases:
            ok = bool(fn(text)) == expected
            passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
            print(f"{'PASS' if ok else 'FAIL'} | {text!r}")

    print("--- escalation ---")
    for level, expected in [
        ("unknown", "self_care"),
        ("self_care", "urgent_care"),
        ("urgent_care", "emergency"),
        ("emergency", "emergency"),
    ]:
        got = escalate(level)
        ok = got == expected
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"{'PASS' if ok else 'FAIL'} | {level} -> {got}")

    print(f"\n{passed} passed, {failed} failed")
