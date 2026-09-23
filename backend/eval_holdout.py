"""Held-out triage cases. NEVER TUNE AGAINST THESE.

WHY A SECOND SET EXISTS
-----------------------
eval_cases.py is the development set. Its failures were read one by one and the
vocabulary was changed until they passed, so its score measures how well the
app fits the cases it was fitted to — which is always going to look good. It
reached 92% that way, and that figure says almost nothing about a description
the app has never seen.

This file is the other half: cases written in one sitting, labelled before any
of them were run, and scored once. The number they produce is the honest one.

THE RULE
--------
Do not change the vocabulary, the rules, or these labels because of how a case
in this file scored. The moment one of these is looked at and fixed, it has been
tuned against and is no longer held out — it becomes a development case with
extra steps, and the score stops meaning anything.

That is why the default report shows only aggregates: how many, how accurate,
and which broad clinical areas are weak. Naming the weak area is fine and is the
point — go and write NEW development cases in that area, fix those, and see
whether the improvement carries over here. That is generalisation, measured
honestly. Reading the failing cases and patching them is not.

WHEN YOU DO NEED TO LOOK
------------------------
    python evaluation.py --holdout --reveal

prints the disagreements, and spends them. Anything revealed must then be moved
into eval_cases.py (fixing it there is fine), and replaced here with a new case
written fresh, in the same area, without looking at the old one. Then update
FINGERPRINT and re-record BASELINE, and say in the commit why.

TAMPER-EVIDENT, NOT TAMPER-PROOF
--------------------------------
FINGERPRINT is a hash of every case below. test_evaluation.py fails if the cases
change without it, so editing a label to improve the score cannot happen
silently: it takes a second, deliberate edit that shows up in review. Nothing
stops it — the aim is only that it is never an accident.

WHAT THIS STILL CANNOT FIX
--------------------------
These were written by the same non-clinician who wrote the rules, the
development cases and the vocabulary, with all of those in mind. Removing the
tuning bias does not remove that one: a wrong assumption shared by rules and
labels still scores as a pass here. Two things fix it, neither of which is code.
A clinician reviewing the labels. And real descriptions from real people, which
/audit/unrecognised will start collecting the day this is used — the only
held-out set nobody involved in building the app wrote.

Recorded 2026-09-21, before the first run.
"""

from eval_cases import Case

# Broad on purpose. A category with one or two cases in it would identify those
# cases, and the sealed report would stop being sealed.
CATEGORIES = (
    "cardiorespiratory",
    "neurological",
    "bleeding_and_injury",
    "infection",
    "children_and_pregnancy",
    "crisis",
    "minor",
    "not_a_symptom",
)

# Plain numbered ids, so no report ever names a case by what it is about.
HOLDOUT = [
    # --- cardiorespiratory --------------------------------------------------
    Case("ho-01", "been getting this tight squeezing feeling behind my breastbone for about half an hour and im all clammy",
         "emergency", "Acute coronary syndrome.", category="cardiorespiratory"),
    Case("ho-02", "my husband has gone grey and sweaty and says it feels like someone is standing on his chest",
         "emergency", "Acute coronary syndrome, reported by a relative.", category="cardiorespiratory"),
    Case("ho-03", "i feel breathless and sick and theres a pain between my shoulder blades",
         "emergency", "Possible MI or aortic dissection.", age=64, category="cardiorespiratory"),
    Case("ho-04", "my sons asthma inhaler is not helping and he can barely get his words out",
         "emergency", "Life-threatening asthma: unable to complete sentences.", age=9, category="cardiorespiratory"),
    Case("ho-05", "heart is pounding really fast and i feel like i might faint",
         "emergency", "Palpitations with near-syncope.", category="cardiorespiratory"),
    Case("ho-06", "not dizzy any more but my chest still really hurts",
         "emergency", "Chest pain; the negation belongs to the dizziness only.", category="cardiorespiratory"),
    Case("ho-07", "my asthma is a bit worse than usual, the inhaler helps but only for a while",
         "urgent_care", "Worsening asthma, still responding to reliever.", category="cardiorespiratory"),
    Case("ho-08", "seene me bahut dard ho raha hai aur pasina aa raha hai",
         "emergency", "Chest pain with sweating, romanised Hindi.", lang="hi", category="cardiorespiratory"),

    # --- neurological -------------------------------------------------------
    Case("ho-09", "mum suddenly cant find her words and her smile has gone lopsided",
         "emergency", "Stroke: speech and facial weakness.", category="neurological"),
    Case("ho-10", "all of a sudden the left side of my body feels numb and heavy",
         "emergency", "Stroke: sudden unilateral sensory and motor change.", category="neurological"),
    Case("ho-11", "he had a fit about ten minutes ago and still hasnt come round properly",
         "emergency", "Seizure with prolonged reduced consciousness.", category="neurological"),
    Case("ho-12", "i banged my head earlier and now i keep being sick and feel really drowsy",
         "emergency", "Head injury with vomiting and drowsiness.", category="neurological"),
    Case("ho-13", "my diabetic dad is really confused and sweaty and wont eat anything",
         "emergency", "Probable hypoglycaemia with confusion.", age=70, category="neurological"),
    Case("ho-14", "bit of a headache after a long day at work, nothing major",
         "self_care", "Tension headache.", category="neurological"),
    Case("ho-15", "मेरे पापा का चेहरा एक तरफ़ लटक गया है और वो बोल नहीं पा रहे",
         "emergency", "Stroke: facial droop and loss of speech, Hindi.", lang="hi", category="neurological"),

    # --- bleeding and injury ------------------------------------------------
    Case("ho-16", "theres a lot of blood coming from a cut on my leg and it wont stop",
         "emergency", "Uncontrolled haemorrhage.", category="bleeding_and_injury"),
    Case("ho-17", "my poo has gone black and sticky and i feel faint when i stand up",
         "emergency", "Melaena with postural symptoms: GI bleed.", category="bleeding_and_injury"),
    Case("ho-18", "i vomited something dark that looked like coffee grounds",
         "emergency", "Upper GI bleed.", category="bleeding_and_injury"),
    Case("ho-19", "my elderly mother fell over and now her hip hurts and she cant stand on it",
         "emergency", "Suspected neck of femur fracture.", age=84, category="bleeding_and_injury"),
    Case("ho-20", "cut my hand on a broken glass, its deep and gaping but the bleeding has stopped",
         "urgent_care", "Laceration needing closure.", category="bleeding_and_injury"),
    Case("ho-21", "think i broke my wrist, its swollen and really painful to move",
         "urgent_care", "Suspected wrist fracture.", category="bleeding_and_injury"),
    Case("ho-22", "twisted my ankle playing football, bit sore but i can still walk on it fine",
         "self_care", "Minor sprain, weight-bearing.", category="bleeding_and_injury"),

    # --- infection ----------------------------------------------------------
    Case("ho-23", "shivering uncontrollably, heart racing and i feel like i am going to pass out",
         "emergency", "Rigors, tachycardia and near-syncope: possible sepsis.", category="infection"),
    Case("ho-24", "stinging when i pee for a few days and now ive got a temperature and pain in my side",
         "urgent_care", "UTI with features of pyelonephritis.", category="infection"),
    Case("ho-25", "my face is swelling up on one side because of a really bad toothache",
         "urgent_care", "Dental abscess with facial swelling.", category="infection"),
    Case("ho-26", "had diarrhoea for a week now and im feeling weak and a bit dizzy",
         "urgent_care", "Prolonged diarrhoea with dehydration symptoms.", duration="days_4_7", category="infection"),
    Case("ho-27", "woke up with my right eye red and painful and things look a bit blurry",
         "urgent_care", "Red painful eye with reduced vision.", category="infection"),
    Case("ho-28", "itchy rash all over since i started some new antibiotics, breathing is fine though",
         "urgent_care", "Drug eruption without airway involvement.", category="infection"),
    Case("ho-29", "runny nose and a bit of a headache, think im getting a cold",
         "self_care", "Upper respiratory infection.", category="infection"),
    Case("ho-30", "slightly sore throat, no temperature, eating and drinking okay",
         "self_care", "Mild pharyngitis; the negation must hold.", category="infection"),
    Case("ho-31", "cough for a couple of days, otherwise feeling alright",
         "self_care", "Minor cough in an older adult with no other features.", age=85, category="infection"),

    # --- children and pregnancy ---------------------------------------------
    Case("ho-32", "my 2 month old is breathing really fast and making a grunting noise",
         "emergency", "Respiratory distress in an infant.", age=0, category="children_and_pregnancy"),
    Case("ho-33", "my toddler drank some bleach from under the sink",
         "emergency", "Caustic ingestion.", age=2, category="children_and_pregnancy"),
    Case("ho-34", "my daughter has a fever and a rash that does not fade when i press a glass on it",
         "emergency", "Non-blanching rash with fever.", age=6, category="children_and_pregnancy"),
    Case("ho-35", "my 2 year old has had a high temperature for three days now",
         "urgent_care", "Persistent fever in an under-five.", age=2, duration="days_1_3",
         category="children_and_pregnancy"),
    Case("ho-36", "im 30 weeks pregnant and bleeding quite heavily",
         "emergency", "Antepartum haemorrhage.", category="children_and_pregnancy"),
    Case("ho-37", "8 weeks pregnant and have been vomiting since this morning, cant keep anything down",
         "urgent_care", "Hyperemesis.", category="children_and_pregnancy"),
    Case("ho-38", "my child doesnt have a rash or a stiff neck, just a runny nose and a cough",
         "self_care", "Minor URTI; both red flags explicitly denied.", age=6, category="children_and_pregnancy"),
    Case("ho-39", "আমার বাচ্চার খিঁচুনি হচ্ছে",
         "emergency", "A child having a seizure, Bengali.", lang="bn", category="children_and_pregnancy"),

    # --- crisis -------------------------------------------------------------
    Case("ho-40", "i keep thinking everyone would be better off if i just disappeared",
         "crisis", "Indirect suicidal ideation.", category="crisis"),
    Case("ho-41", "ive been giving my things away and writing goodbye letters to my family",
         "crisis", "Behavioural warning signs of suicide.", category="crisis"),
    Case("ho-42", "whats the point anymore, i just want to go to sleep and never wake up",
         "crisis", "Passive suicidal ideation.", category="crisis"),
    Case("ho-43", "i have been cutting my arms to cope with everything",
         "crisis", "Self-harm.", category="crisis"),
    Case("ho-44", "i took a whole packet of paracetamol about an hour ago",
         "emergency", "Overdose. The medical emergency comes first: sending only a "
         "counselling number here would be a failure, so crisis scores as wrong.",
         category="crisis"),
    Case("ho-45", "সব কিছু শেষ করে দিতে ইচ্ছে করছে",
         "crisis", "Wanting to end everything, Bengali.", lang="bn", category="crisis"),
    Case("ho-46", "मुझे लगता है मेरे न रहने से सबका भला होगा",
         "crisis", "Everyone would be better off without me, Hindi.", lang="hi", category="crisis"),

    # --- minor --------------------------------------------------------------
    Case("ho-47", "sore muscles after the gym yesterday",
         "self_care", "Exercise-related muscle soreness.", category="minor"),
    Case("ho-48", "hay fever is playing up, sneezing and itchy eyes",
         "self_care", "Allergic rhinitis.", category="minor"),
    Case("ho-49", "i found a small lump in my breast last week, it doesnt hurt",
         "self_care", "Needs a doctor's appointment, not same-day care.", category="minor"),
    Case("ho-50", "হালকা সর্দি আর নাক বন্ধ",
         "self_care", "Mild cold and blocked nose, Bengali.", lang="bn", category="minor"),

    # --- not a symptom ------------------------------------------------------
    Case("ho-51", "do you have a lady doctor available on saturday morning",
         "unknown", "Administrative.", category="not_a_symptom"),
    Case("ho-52", "how much does a blood test usually cost",
         "unknown", "Administrative. Contains 'blood'.", category="not_a_symptom"),
    Case("ho-53", "my chest x-ray came back normal, what does that mean",
         "unknown", "Contains 'chest' with no symptom attached.", category="not_a_symptom"),
    Case("ho-54", "i am writing a school project about heart attacks",
         "unknown", "Names an emergency without having one.", category="not_a_symptom"),
    Case("ho-55", "i need a medical certificate for my employer",
         "unknown", "Administrative.", category="not_a_symptom"),
]

# A hash of every case above. See "TAMPER-EVIDENT" in the module docstring.
FINGERPRINT = "e04af4d42a0c"

# The first and only blind run. Regression guards compare against this; nothing
# may be tuned to raise it. Tied to the fingerprint it was measured on, so a
# changed set with a stale baseline fails the tests instead of comparing two
# different things.
#
# For the record, the same run scored the development set at 92.3% exact with no
# dangerous misses. The gap between the two is the measure of how much of that
# 92% was fitting rather than understanding: almost all of it. Every crisis case
# here failed, including phrasings of exactly the kind the development set's
# crisis fixes were written for.
BASELINE = {
    "recorded": "2026-09-21",
    "fingerprint": "e04af4d42a0c",
    "total": 55,
    "exact": 23,
    "dangerous": 25,
}
