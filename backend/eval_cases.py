"""Labelled cases for measuring triage accuracy.

WHAT THIS IS FOR
----------------
The unit tests check that the code does what it was written to do. Nothing in
them asks whether what it was written to do is right. These cases are the other
question: given a description a real person might type, does the app reach the
grade a competent triage nurse would?

HOW THE LABELS WERE SET, AND WHY THAT MATTERS
---------------------------------------------
From the same commonly published warning signs the rules themselves came from,
by the same non-clinician. So this measures consistency, not correctness: where
a rule and its label share a wrong assumption, this file will happily agree with
it and report a pass.

That is a real limitation and it is not a reason to skip the exercise. Two
things still hold:

  1. The *shape* of the errors is informative regardless of label quality.
     Under-triage and over-triage are not symmetric, and counting them
     separately says something true about the system's disposition.

  2. This is the artefact a clinician can actually review. Reading 6,000 lines
     of rules is a project; reading fifty labelled vignettes and saying "no,
     that one is an emergency" is an afternoon. When that review happens, the
     labels here are what changes, and the score moves with them.

PHRASING
--------
Written the way people write, not the way the vocabulary is spelled. The unit
tests already cover the vocabulary; these deliberately use colloquial,
roundabout and partial descriptions, because that is what arrives in practice.

Cases marked `expected_miss` are ones the app is known not to get. They are kept
rather than deleted: a known gap that is measured every run is a different thing
from a gap nobody has written down.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    expected: str
    why: str
    lang: str = "en"
    age: Optional[int] = None
    duration: Optional[str] = None
    # Set when the app is known to disagree, with the reason. Counted and
    # reported separately rather than quietly excluded.
    expected_miss: bool = False


CASES = [
    # --- emergency: cardiac -------------------------------------------------
    Case(
        "mi-classic",
        "crushing pain in the middle of my chest and it is going down my left arm, I am sweating",
        "emergency",
        "Textbook myocardial infarction presentation.",
    ),
    Case(
        "mi-atypical-elderly",
        "I feel very tired and a bit sick and my jaw is aching",
        "emergency",
        "Atypical MI, common in older adults and in women: no chest pain at all. "
        "The vocabulary has no jaw pain, so this reads as fatigue and nausea.\n"
        "        THE FIX, and why it is not just a phrase: jaw pain was briefly "
        "added to chest_pain, which made this case pass. It was removed again "
        "because the result panel would then have told someone who wrote 'my "
        "jaw is aching' that the app understood 'Chest pain'. It needs a "
        "jaw_pain symptom of its own, translated into all three languages, "
        "joined to fatigue and nausea by a cardiac rule for older adults.",
        age=72,
        expected_miss=True,
    ),
    Case(
        "breathless-rest",
        "I cannot catch my breath even when I am just sitting still",
        "emergency",
        "Breathlessness at rest.",
    ),
    Case(
        "blue-lips",
        "his lips have gone a bit blue and he is breathing fast",
        "emergency",
        "Cyanosis: hypoxia until proven otherwise.",
    ),

    # --- emergency: stroke --------------------------------------------------
    Case(
        "stroke-face-arm",
        "my dad's face has dropped on one side and he cannot lift his right arm",
        "emergency",
        "FAST positive.",
    ),
    Case(
        "stroke-speech",
        "his words are coming out all slurred and jumbled",
        "emergency",
        "Speech disturbance.",
    ),
    Case(
        "stroke-vision",
        "I have suddenly lost the sight in one eye",
        "emergency",
        "Sudden monocular vision loss.",
    ),

    # --- emergency: neurological / sepsis -----------------------------------
    Case(
        "thunderclap",
        "the worst headache I have ever had, it came on in seconds like being hit",
        "emergency",
        "Thunderclap headache: possible subarachnoid haemorrhage.",
    ),
    Case(
        "meningitis-triad",
        "high fever, my neck is stiff and the light is hurting my eyes",
        "emergency",
        "Meningitis triad.",
    ),
    Case(
        "sepsis-confusion",
        "she has a fever and she is confused and not making sense",
        "emergency",
        "Fever with new confusion suggests sepsis.",
        age=78,
    ),

    # --- emergency: bleeding ------------------------------------------------
    Case(
        "haemoptysis",
        "I coughed up blood this morning",
        "emergency",
        "Haemoptysis.",
    ),
    Case(
        "haematemesis",
        "I have been vomiting and there was blood in it",
        "emergency",
        "Haematemesis, but stated across two clauses: 'it' refers back to the "
        "vomit. Matching is on contiguous word runs, so resolving that needs "
        "pronoun resolution the extractor does not do. Grades urgent_care from "
        "the vomiting alone. Deliberately not fixed by adding 'blood in it', "
        "which would fire on any mention of blood in anything.",
        expected_miss=True,
    ),

    # --- emergency: paediatric ----------------------------------------------
    Case(
        "infant-floppy",
        "my baby has gone floppy and will not wake up properly",
        "emergency",
        "Reduced consciousness in an infant.",
        age=0,
    ),
    Case(
        "infant-fever",
        "my six week old has a temperature",
        "emergency",
        "Fever under three months is an emergency regardless of how well they look.",
        age=0,
    ),

    # --- emergency stated in plain language ---------------------------------
    Case(
        "collapsed",
        "my father collapsed and is not responding",
        "emergency",
        "Caught by the plain-language override rather than the vocabulary.",
    ),
    Case(
        "not-breathing",
        "he is not breathing properly and I cannot wake him",
        "emergency",
        "Override.",
    ),

    # --- urgent care --------------------------------------------------------
    Case(
        "chest-infection",
        "fever and a bad cough for four days and I feel worse today",
        "urgent_care",
        "Likely chest infection, same-day assessment.",
        duration="days_4_7",
    ),
    Case(
        "uti",
        "it burns when I pee and my lower back aches",
        "urgent_care",
        "UTI with possible upper tract involvement.",
    ),
    Case(
        "septic-joint",
        "my knee is swollen and red and hot and I cannot put weight on it",
        "urgent_care",
        "Hot swollen joint.",
    ),
    Case(
        "dehydration-risk",
        "vomiting and diarrhoea since yesterday and I cannot keep water down",
        "urgent_care",
        "Dehydration risk.",
    ),
    Case(
        "tb-screen",
        "I have had a cough for over three weeks and I am losing weight",
        "urgent_care",
        "The Indian TB screening threshold.",
        duration="weeks_over_3",
    ),
    Case(
        "appendicitis",
        "pain in the lower right of my tummy that has been getting worse all day",
        "urgent_care",
        "Possible appendicitis. Depends on the follow-up question to escalate.",
    ),
    Case(
        "child-diarrhoea",
        "my three year old has had diarrhoea all day",
        "urgent_care",
        "Under-fives dehydrate fast.",
        age=3,
    ),
    Case(
        "elderly-fever",
        "I have had a fever since this morning",
        "urgent_care",
        "Older adults deteriorate atypically, so the same fever grades higher.",
        age=79,
    ),

    # --- self care ----------------------------------------------------------
    Case(
        "common-cold",
        "runny nose and a bit of a sore throat since this morning",
        "self_care",
        "Ordinary upper respiratory infection.",
        duration="today",
    ),
    Case(
        "tension-headache",
        "mild headache after staring at a screen all day",
        "self_care",
        "Tension headache.",
        duration="today",
    ),
    Case(
        "mild-cough",
        "slight cough, no fever, feeling fine otherwise",
        "self_care",
        "Minor, and the negation must hold.",
        duration="days_1_3",
    ),
    Case(
        "sore-throat-adult",
        "my throat hurts when I swallow",
        "self_care",
        "Pharyngitis in a well adult.",
        age=30,
    ),
    Case(
        "mild-back",
        "my lower back has been aching since I lifted something heavy",
        "self_care",
        "Mechanical back pain with no red flags.",
    ),

    # --- negation and distractors ------------------------------------------
    Case(
        "negated-chest-pain",
        "no chest pain but I have had a cough for a month",
        "urgent_care",
        "The denial must not be read as a symptom, and a month of cough still "
        "meets the TB threshold.",
        duration="weeks_over_3",
    ),
    Case(
        "denied-fever",
        "I do not have a fever, just a blocked nose",
        "self_care",
        "Negation over-reaches. 'blocked nose' matches on its own, and the "
        "existing 'no trouble breathing, just a cough' case passes, but here the "
        "denial swallows the appositive too and nothing is extracted. The "
        "difference is the parse: 'do not have' attaches the negation to the "
        "verb, so both objects sit inside its subtree without crossing a "
        "scope-breaking edge. Fails safe — the result is 'not understood', not a "
        "wrong grade — so it is recorded rather than patched around.",
        expected_miss=True,
    ),
    Case(
        "admin-question",
        "I want to book an appointment with a skin doctor",
        "unknown",
        "Not a symptom description. Must not invent a grade.",
    ),
    Case(
        "opening-hours",
        "what time does the clinic open",
        "unknown",
        "Not a symptom description.",
    ),
    Case(
        "phone-number",
        "can I have the phone number please",
        "unknown",
        "Contains 'number', which must not read as numbness.",
    ),

    # --- crisis -------------------------------------------------------------
    Case(
        "crisis-plain",
        "I do not want to be here anymore",
        "crisis",
        "Passive suicidal ideation, phrased indirectly.",
    ),
    Case(
        "crisis-direct",
        "I want to kill myself",
        "crisis",
        "Direct.",
    ),

    # --- multilingual -------------------------------------------------------
    Case(
        "hi-chest",
        "मुझे सीने में तेज़ दर्द हो रहा है और साँस नहीं आ रही",
        "emergency",
        "Chest pain and breathlessness in Hindi.",
        lang="hi",
    ),
    Case(
        "bn-chest",
        "আমার বুকে খুব ব্যথা করছে আর শ্বাস নিতে পারছি না",
        "emergency",
        "Chest pain and breathlessness in Bengali.",
        lang="bn",
    ),
    Case(
        "hi-crisis",
        "मैं अब जीना नहीं चाहता",
        "crisis",
        "Suicidal ideation in Hindi must reach the counselling path.",
        lang="hi",
    ),
    Case(
        "bn-crisis",
        "আমি আর বাঁচতে চাই না",
        "crisis",
        "Suicidal ideation in Bengali.",
        lang="bn",
    ),
    Case(
        "hi-fever-cough",
        "मुझे बुखार और खांसी है",
        "urgent_care",
        "Fever with cough in Hindi.",
        lang="hi",
    ),
    Case(
        "bn-mild",
        "আমার সামান্য গলা ব্যথা",
        "self_care",
        "A design limit rather than a defect: the offline Indic table holds red "
        "flags and crisis language only, so ordinary Bengali complaints are not "
        "extracted without the LLM. Deliberate — the offline path was built to "
        "catch what is dangerous in every language, not to be a second full "
        "vocabulary. Worth measuring so the cost of that choice stays visible.",
        lang="bn",
        expected_miss=True,
    ),

    # --- known gaps ---------------------------------------------------------
    Case(
        "dka",
        "I am very thirsty all the time, passing a lot of urine and losing weight",
        "urgent_care",
        "New diabetes, possibly ketoacidosis. Reaches the right grade, but for "
        "an incomplete reason: it extracts dehydration and weight loss, and "
        "grades on those. The polyuria is not read at all and nothing connects "
        "the triad. Scored as a pass because the grade is what the patient acts "
        "on — worth knowing the reasoning underneath is thinner than the result "
        "suggests, which is exactly what a clinician reviewing this would want "
        "flagged.",
    ),
    Case(
        "ectopic",
        "sharp pain low on one side and my period is late",
        "emergency",
        "Possible ectopic pregnancy. Missed period is known; one-sided pelvic "
        "pain is not, and the pair is not a curated rule.",
        expected_miss=True,
    ),
    Case(
        "anaphylaxis",
        "my lips and tongue are swelling up after eating peanuts",
        "emergency",
        "Anaphylaxis. Allergic reaction exists in the vocabulary but airway "
        "swelling is not distinguished from a rash.",
        expected_miss=True,
    ),
    Case(
        "testicular-torsion",
        "sudden severe pain in my testicle since an hour ago",
        "emergency",
        "Torsion is a surgical emergency with a six hour window. Not in the "
        "vocabulary.",
        expected_miss=True,
    ),
]


LEVEL_ORDER = ["unknown", "self_care", "urgent_care", "emergency"]
