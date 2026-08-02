"""Extraction tests. Run: python -m pytest test_nlp_utils.py  (or: python test_nlp_utils.py)"""

from nlp_utils import extract_symptoms
from symptoms import SYMPTOM_PHRASES

CASES = [
    # baseline
    ("I have chest pain and difficulty breathing", ["chest_pain", "difficulty_breathing"]),
    ("I have a fever and a bad cough", ["cough", "fever"]),
    ("I feel nauseous and dizzy", ["dizziness", "nausea"]),
    ("I don't feel like myself today", []),
    # word-form variation, handled by lemmatization
    ("I've been coughing all night", ["cough"]),
    ("my chest hurts really bad", ["chest_pain"]),
    # vomiting is its own symptom, separate from nausea: actually being sick
    # carries a dehydration risk that merely feeling sick does not.
    ("I keep vomiting", ["vomiting"]),
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
    # "want to throw up" is arguably nausea rather than vomiting, but the
    # phrasing matches vomiting and that is the more urgent of the two — an
    # acceptable over-read given the escalate-when-uncertain rule.
    ("feeling lightheaded and want to throw up", ["dizziness", "vomiting"]),
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
    ("itchy skin and red spots", ["itching", "rash"]),
    # red flags
    ("my speech is slurred", ["slurred_speech"]),
    # Both are true here, and both are worth surfacing — the stroke sign is what
    # drives the urgency either way.
    ("my face is drooping and my arm went numb", ["numbness", "one_sided_weakness"]),
    ("stiff neck and a terrible headache", ["headache", "neck_stiffness"]),
    ("he seems confused and disoriented", ["confusion"]),
    # negation still holds with the larger vocabulary
    ("no headache, just a sore throat", ["sore_throat"]),
    # --- symptom families added in the expansion to 79 ------------------------
    ("burning when I pee", ["painful_urination"]),
    ("there is blood in my urine", ["blood_in_urine"]),
    ("my knee is swollen", ["joint_swelling"]),
    ("knee pain for weeks now", ["joint_pain"]),
    ("terrible toothache on the left side", ["toothache"]),
    ("ringing in my ears for a week", ["hearing_loss"]),
    ("my eyes look yellow", ["jaundice"]),
    # Both are literally true, and the specific one is what drives the urgency.
    ("coughing up blood this morning", ["cough", "coughing_blood"]),
    ("my heart is racing", ["palpitations"]),
    ("swollen ankles by the evening", ["leg_swelling"]),
    ("I have not been able to sleep for days", ["insomnia"]),
    ("my period is late", ["missed_period"]),
    ("the baby is floppy and will not feed", ["child_lethargy", "child_not_feeding"]),
    ("lump in my neck that will not go", ["lump", "swollen_glands"]),
    ("losing weight and sweating at night", ["night_sweats", "weight_loss"]),
]

# Inputs that must NOT produce a symptom. With 79 symptoms the fuzzy matcher
# has far more opportunity to collide, so these guard against false positives.
NEGATIVE_CASES = [
    "I want to book an appointment",
    "what are your opening hours",
    "my neighbour asked me to test this app",
    "the weather is nice today",
    "thanks for the help",
    "I need a phone number for the clinic",
    "is there a doctor available today",
]

# Phrases that fuzzy matching used to spray across unrelated symptoms, because
# partial_ratio ignores word boundaries. Each entry is (text, must-not-appear).
# These are the cases that forced the switch to anchored n-gram matching, so a
# regression here means that change has been undone.
COLLISION_CASES = [
    # "burn" is a substring of "burning", but this is a urine infection.
    ("burning when I urinate", "burn"),
    # The swollen-* family all share a prefix and used to match together.
    ("swollen legs", "allergic_reaction"),
    ("swollen legs", "swollen_glands"),
    ("swollen legs", "toothache"),
    # Pain phrases differ only in the body part.
    ("back pain", "ear_pain"),
    ("back pain", "eye_pain"),
    ("back pain", "neck_pain"),
    # "numb" inside "number".
    ("what is your phone number", "numbness"),
    # A typo must land on one symptom, not every phrase ending in "pain".
    ("chets pain", "abdominal_pain"),
    ("chets pain", "pregnancy_pain"),
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


def test_no_phrase_collisions():
    failures = []
    for text, forbidden in COLLISION_CASES:
        got = extract_symptoms(text)
        if forbidden in got:
            failures.append(f"{text!r} wrongly matched {forbidden!r} (got {got})")
    assert not failures, "\n".join(failures)


def test_every_phrase_finds_its_own_symptom():
    """Every phrase in the vocabulary must extract the symptom that owns it.

    Cheap to run and the single most useful guard on symptoms.py: it catches a
    phrase that a lemma mismatch or a shadowing entry has made unreachable, which
    is otherwise invisible until a real user is not understood.
    """
    failures = []
    for symptom, phrases in SYMPTOM_PHRASES.items():
        for phrase in phrases:
            got = extract_symptoms(phrase)
            if symptom not in got:
                failures.append(f"{symptom}: {phrase!r} extracted {got}")
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

    print("\n--- phrase collision checks ---")
    for text, forbidden in COLLISION_CASES:
        got = extract_symptoms(text)
        ok = forbidden not in got
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        print(f"{'PASS' if ok else 'FAIL'} | {text!r} must not match {forbidden}")
        if not ok:
            print(f"       got {got}")

    print("\n--- every phrase finds its own symptom ---")
    unreachable = []
    total_phrases = 0
    for symptom, phrases in SYMPTOM_PHRASES.items():
        for phrase in phrases:
            total_phrases += 1
            if symptom not in extract_symptoms(phrase):
                unreachable.append((symptom, phrase))
    if unreachable:
        failed += len(unreachable)
        for symptom, phrase in unreachable:
            print(f"FAIL | {symptom}: {phrase!r} does not extract itself")
    else:
        passed += 1
        print(f"PASS | all {total_phrases} phrases across "
              f"{len(SYMPTOM_PHRASES)} symptoms extract themselves")

    print(f"\n{passed} passed, {failed} failed")
