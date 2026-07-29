"""Urgency rule tests. Run: python test_knowledge_graph.py"""

from knowledge_graph import assess_urgency

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
]


def test_urgency():
    failures = []
    for symptoms, expected in CASES:
        got = assess_urgency(symptoms)["level"]
        if got != expected:
            failures.append(f"{symptoms} -> got {got!r}, expected {expected!r}")
    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    passed = failed = 0
    for symptoms, expected in CASES:
        got = assess_urgency(symptoms)["level"]
        ok = got == expected
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"{'PASS' if ok else 'FAIL'} | {symptoms} -> {got}")
        if not ok:
            print(f"       expected {expected}")
    print(f"\n{passed} passed, {failed} failed")
