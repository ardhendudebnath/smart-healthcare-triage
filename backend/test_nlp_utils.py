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
]


def test_extraction():
    failures = []
    for text, expected in CASES:
        got = extract_symptoms(text)
        if got != sorted(expected):
            failures.append(f"{text!r}\n  got={got} expected={sorted(expected)}")
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
    print(f"\n{passed} passed, {failed} failed")
