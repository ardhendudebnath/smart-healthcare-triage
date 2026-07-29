"""Extraction tests. Run: python -m pytest test_nlp_utils.py  (or: python test_nlp_utils.py)"""

from nlp_utils import extract_symptoms

CASES = [
    # baseline
    ("I have chest pain and difficulty breathing", ["chest_pain", "difficulty_breathing"]),
    ("I have a fever and a bad cough", ["cough", "fever"]),
    ("I feel nauseous and dizzy", ["dizziness", "nausea"]),
    ("I don't feel like myself today", []),
    # word-form variation, handled by lemmatization
    ("I've been coughing all night", ["cough"]),
    ("my chest hurts really bad", ["chest_pain"]),
    ("I keep vomiting", ["nausea"]),
    ("feeling really feverish", ["fever"]),
    # negation — symptom explicitly denied
    ("I have no fever but I do have a cough", ["cough"]),
    ("no chest pain, just a cough", ["cough"]),
    ("I don't have a fever", []),
    ("no trouble breathing, just a cough", ["cough"]),
    # typos, handled by fuzzy matching
    ("chets pain and truble breathing", ["chest_pain", "difficulty_breathing"]),
    ("i have feverr", ["fever"]),
    # informal phrasing
    ("cant breathe properly and my chest is tight", ["chest_pain", "difficulty_breathing"]),
    ("feeling lightheaded and want to throw up", ["dizziness", "nausea"]),
    ("short of breath", ["difficulty_breathing"]),
    # "can't breathe" is an emergency symptom, not a denial of one. spaCy
    # tokenizes it as ca/nt/breathe, so a naive negation check drops it.
    ("I can't breathe", ["difficulty_breathing"]),
    ("I cant breathe", ["difficulty_breathing"]),
    ("cannot breathe and chest pain", ["chest_pain", "difficulty_breathing"]),
    # newly added symptoms
    ("my head is killing me", ["headache"]),
    ("bad migraine since morning", ["headache"]),
    ("stomach ache and loose motions", ["abdominal_pain", "diarrhea"]),
    ("sore throat and it hurts to swallow", ["sore_throat"]),
    ("I feel exhausted with no energy", ["fatigue"]),
    ("itchy skin and red spots", ["rash"]),
    # red flags
    ("my speech is slurred", ["slurred_speech"]),
    ("my face is drooping and my arm went numb", ["one_sided_weakness"]),
    ("stiff neck and a terrible headache", ["headache", "neck_stiffness"]),
    ("he seems confused and disoriented", ["confusion"]),
    # negation still holds with the larger vocabulary
    ("no headache, just a sore throat", ["sore_throat"]),
]

# Inputs that must NOT produce a symptom. With 16 symptoms the fuzzy matcher
# has far more opportunity to collide, so these guard against false positives.
NEGATIVE_CASES = [
    "I want to book an appointment",
    "what are your opening hours",
    "my neighbour asked me to test this app",
    "the weather is nice today",
    "thanks for the help",
]


def test_extraction():
    failures = []
    for text, expected in CASES:
        got = extract_symptoms(text)
        if got != sorted(expected):
            failures.append(f"{text!r}\n  got={got} expected={sorted(expected)}")
    assert not failures, "\n".join(failures)


def test_no_false_positives():
    failures = []
    for text in NEGATIVE_CASES:
        got = extract_symptoms(text)
        if got:
            failures.append(f"{text!r} wrongly matched {got}")
    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    passed = failed = 0
    for text, expected in CASES:
        got = extract_symptoms(text)
        ok = got == sorted(expected)
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"{'PASS' if ok else 'FAIL'} | {text!r}")
        if not ok:
            print(f"       got={got} expected={sorted(expected)}")

    print("\n--- false positive checks ---")
    for text in NEGATIVE_CASES:
        got = extract_symptoms(text)
        ok = not got
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"{'PASS' if ok else 'FAIL'} | {text!r}")
        if not ok:
            print(f"       wrongly matched {got}")

    print(f"\n{passed} passed, {failed} failed")
