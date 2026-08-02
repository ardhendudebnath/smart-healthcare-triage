"""Urgency rules.

Deliberately deterministic: the LLM only turns text into symptom names, and
every triage decision is made here so it is reproducible and testable.

IMPORTANT: these rules are built from commonly published warning signs (stroke
FAST signs, meningitis red flags, sepsis indicators). They are a prototype and
have NOT been reviewed by a clinician. Do not use for real triage without
medical review.

Design rule: when in doubt, escalate. Under-triage (telling someone with a
stroke to rest at home) is far more dangerous than over-triage.

How the four layers fit together
--------------------------------
With 79 symptoms there are over 3,000 possible pairs, so listing every
combination is no longer an option. Instead:

  1. EMERGENCY_SINGLE  -- symptoms that mean "go now" on their own.
  2. EMERGENCY_COMBOS  -- pairs that are only dangerous together.
  3. URGENT_CARE_COMBOS -- pairs of otherwise-ordinary symptoms that together
                           warrant being seen the same day.
  4. Weight fallback   -- for the thousands of combinations nobody curated:
                          any CONCERNING symptom, or enough ordinary ones
                          stacked up, means same-day care.

Curated rules always win, so the fallback can only ever be the reason a result
came out *more* urgent than "see your GP" -- never less.

Keeping the rule table honest
-----------------------------
Because the layers are checked in order, a rule can become unreachable without
anyone noticing -- for example an urgent-care pair whose member is already
CONCERNING on its own is dead code, since the weight fallback would have caught
it anyway. test_knowledge_graph.py asserts every curated rule is still
reachable, so the table cannot quietly rot as symptoms are added.
"""

from typing import Dict, FrozenSet, List, Tuple

from symptoms import CONCERNING, label_of, weight_of

# Symptoms serious enough to warrant emergency care on their own.
#
# Chest pain and breathlessness are here rather than in the combo list because
# published patient guidance treats either alone as a reason to call an
# ambulance. That is a deliberate over-triage: most chest pain is not cardiac,
# but the cost of missing the cases that are is not comparable.
EMERGENCY_SINGLE = {
    # Stroke — time to treatment determines the outcome.
    "slurred_speech",
    "one_sided_weakness",
    "vision_loss",
    # Cardiac and respiratory.
    "chest_pain",
    "difficulty_breathing",
    "bluish_lips",
    # Bleeding from the airway or gut.
    "coughing_blood",
    "vomiting_blood",
    # Neurological.
    "seizure_symptom",
    # Airway swelling.
    "allergic_reaction",
    # Acute urinary retention.
    "unable_to_urinate",
    # Obstetric — both need assessment the same hour, not the same day.
    "pregnancy_bleeding",
    "pregnancy_pain",
    # Babies deteriorate fast and show fewer signs than adults.
    "child_lethargy",
    "child_not_feeding",
    # Open or displaced fracture.
    "injury_fracture",
}

# Pairs where neither symptom alone is an emergency but the combination is.
# Every symptom named here must stay out of EMERGENCY_SINGLE or the rule becomes
# unreachable.
# Each entry carries a stable key alongside its English text. The key is what
# i18n.py translates against: rewording the English must not silently orphan the
# Hindi and Bengali versions, and a key that no longer exists is visible in
# test_i18n.py rather than showing up as an English sentence in a Bengali UI.
EMERGENCY_COMBOS: List[Tuple[FrozenSet[str], str, str]] = [
    (
        frozenset({"headache", "neck_stiffness"}),
        "meningitis_headache",
        "A headache with a stiff neck can indicate meningitis.",
    ),
    (
        frozenset({"fever", "neck_stiffness"}),
        "meningitis_fever",
        "A fever with a stiff neck can indicate meningitis.",
    ),
    (
        frozenset({"confusion", "neck_stiffness"}),
        "meningitis_confusion",
        "Confusion with a stiff neck can indicate meningitis.",
    ),
    (
        frozenset({"fever", "rash"}),
        "sepsis_rash",
        "A fever with a rash can indicate a serious blood infection.",
    ),
    (
        frozenset({"confusion", "fever"}),
        "sepsis_confusion",
        "Confusion alongside a fever can indicate sepsis.",
    ),
    (
        frozenset({"confusion", "dehydration"}),
        "sepsis_dehydration",
        "Confusion with dehydration can indicate a serious infection.",
    ),
    (
        frozenset({"confusion", "headache"}),
        "brain_bleed",
        "Confusion with a severe headache can indicate bleeding on the brain.",
    ),
    (
        frozenset({"headache", "double_vision"}),
        "raised_pressure",
        "A headache with vision changes can indicate pressure inside the skull.",
    ),
    (
        frozenset({"numbness", "balance_problems"}),
        "stroke_numbness",
        "Numbness with loss of balance can be a stroke sign.",
    ),
    (
        frozenset({"double_vision", "balance_problems"}),
        "stroke_vision",
        "Vision changes with loss of balance can be a stroke sign.",
    ),
    (
        frozenset({"fainting", "palpitations"}),
        "cardiac_syncope",
        "Fainting with an irregular heartbeat can indicate a heart rhythm problem.",
    ),
    (
        frozenset({"jaundice", "abdominal_pain"}),
        "biliary",
        "Yellow skin with stomach pain can indicate a blocked bile duct.",
    ),
    (
        frozenset({"jaundice", "fever"}),
        "cholangitis",
        "Yellow skin with a fever can indicate a serious liver or bile infection.",
    ),
    (
        frozenset({"eye_pain", "double_vision"}),
        "glaucoma",
        "Eye pain with vision changes can indicate acute glaucoma.",
    ),
]

# Pairs of ordinary symptoms that together mean same-day care. Members must all
# be below CONCERNING — a CONCERNING symptom already reaches urgent care through
# the weight fallback, which would make the rule unreachable.
URGENT_CARE_COMBOS: List[Tuple[FrozenSet[str], str, str]] = [
    (
        frozenset({"fever", "cough"}),
        "chest_infection",
        "A fever with a cough may be a chest infection.",
    ),
    (
        frozenset({"fever", "headache"}),
        "fever_headache",
        "A fever with a headache should be assessed today.",
    ),
    (
        frozenset({"fever", "sore_throat"}),
        "fever_throat",
        "A fever with a sore throat may need treatment.",
    ),
    (
        frozenset({"fever", "diarrhea"}),
        "fever_diarrhea",
        "A fever with diarrhoea may be an infection needing treatment.",
    ),
    (
        frozenset({"fever", "ear_pain"}),
        "fever_ear",
        "A fever with earache may be an ear infection.",
    ),
    (
        # Fever with aching joints or muscles is the classic dengue and
        # chikungunya presentation, which matters a great deal in India.
        frozenset({"fever", "joint_pain"}),
        "dengue_joint",
        "A fever with joint pain should be assessed today — it can indicate dengue.",
    ),
    (
        frozenset({"fever", "muscle_pain"}),
        "dengue_muscle",
        "A fever with body aches should be assessed today — it can indicate dengue.",
    ),
    (
        frozenset({"nausea", "dizziness"}),
        "nausea_dizzy",
        "Feeling sick and dizzy together should be assessed today.",
    ),
    (
        frozenset({"diarrhea", "nausea"}),
        "dehydration_risk",
        "Diarrhoea with sickness risks dehydration.",
    ),
    (
        # Dehydration risk, particularly in children and older adults.
        frozenset({"diarrhea", "dizziness"}),
        "dehydration_dizzy",
        "Diarrhoea with dizziness suggests you may be dehydrated.",
    ),
    (
        # New-onset diabetes commonly presents this way.
        frozenset({"frequent_urination", "fatigue"}),
        "diabetes_screen",
        "Passing urine often alongside tiredness should be checked today.",
    ),
]

# The two reasons that name specific symptoms rather than reading as a fixed
# sentence. They are templates so a translation can put {names} where its own
# grammar needs it, instead of assuming English word order.
REASON_TEMPLATES = {
    "emergency_single": "Needs emergency assessment: {names}.",
    "urgent_weight": "Should be seen today: {names}.",
}

# Enough ordinary symptoms stacked together justify same-day care even with no
# curated rule. Three is the point where "a bit of everything" stops looking
# like a mild self-limiting illness.
SCORE_THRESHOLD = 3

MESSAGES = {
    "emergency": (
        "These symptoms can indicate a serious condition. Please go to the "
        "emergency room or call emergency services now."
    ),
    "urgent_care": (
        "These symptoms should be seen the same day. Please visit an urgent "
        "care clinic."
    ),
    "self_care": (
        "These symptoms are best checked by your regular doctor. Book a "
        "routine appointment."
    ),
    "unknown": (
        "I couldn't identify clear symptoms. Could you describe how you're "
        "feeling in more detail?"
    ),
}


def _result(
    level: str,
    reason: str = "",
    reason_key: str = "",
    reason_symptoms: List[str] = None,
) -> Dict:
    """One triage verdict.

    `reason` is the English explanation and `reason_key` identifies which rule
    produced it, so i18n.py can swap in a translation without this module
    knowing that other languages exist. `reason_symptoms` carries the ids the
    two templated reasons name, because their labels have to be translated too.
    """
    return {
        "level": level,
        "message": MESSAGES[level],
        "reason": reason,
        "reason_key": reason_key,
        "reason_symptoms": reason_symptoms or [],
    }


def assess_urgency(symptoms: List[str]) -> Dict:
    """Map a set of symptoms to an urgency level.

    Checked most severe first, so the highest applicable level always wins. The
    returned `reason` explains which rule fired, so the frontend can tell the
    user why rather than just handing down a verdict.
    """
    symptom_set = set(symptoms)

    triggered = symptom_set & EMERGENCY_SINGLE
    if triggered:
        ordered = sorted(triggered)
        names = ", ".join(label_of(s).lower() for s in ordered)
        return _result(
            "emergency",
            REASON_TEMPLATES["emergency_single"].format(names=names),
            "emergency_single",
            ordered,
        )

    for combo, key, reason in EMERGENCY_COMBOS:
        if combo.issubset(symptom_set):
            return _result("emergency", reason, key)

    for combo, key, reason in URGENT_CARE_COMBOS:
        if combo.issubset(symptom_set):
            return _result("urgent_care", reason, key)

    if not symptom_set:
        return _result("unknown")

    # Weight fallback for uncurated combinations.
    concerning = sorted(s for s in symptom_set if weight_of(s) >= CONCERNING)
    if concerning:
        names = ", ".join(label_of(s).lower() for s in concerning)
        return _result(
            "urgent_care",
            REASON_TEMPLATES["urgent_weight"].format(names=names),
            "urgent_weight",
            concerning,
        )

    if sum(weight_of(s) for s in symptom_set) >= SCORE_THRESHOLD:
        return _result(
            "urgent_care",
            "Several symptoms at once are worth having looked at today.",
            "several_symptoms",
        )

    return _result("self_care")
