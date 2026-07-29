"""Urgency rules.

Deliberately deterministic: the LLM only turns text into symptom names, and
every triage decision is made here so it is reproducible and testable.

IMPORTANT: these rules are built from commonly published warning signs (stroke
FAST signs, meningitis red flags, sepsis indicators). They are a prototype and
have NOT been reviewed by a clinician. Do not use for real triage without
medical review.

Design rule: when in doubt, escalate. Under-triage (telling someone with a
stroke to rest at home) is far more dangerous than over-triage.
"""

from typing import Dict, List

# Symptoms serious enough to warrant emergency care on their own. Stroke signs
# especially — for these, time to treatment is what determines the outcome.
EMERGENCY_SINGLE = {
    "slurred_speech",
    "one_sided_weakness",
}

EMERGENCY_COMBOS = [
    {"chest_pain", "difficulty_breathing"},
    {"difficulty_breathing", "fever"},
    # Classic cardiac presentation — chest pain with nausea or sweating.
    {"chest_pain", "nausea"},
    # Possible meningitis.
    {"headache", "neck_stiffness"},
    {"fever", "neck_stiffness"},
    # Altered mental state with infection — possible sepsis.
    {"confusion", "fever"},
    # Confusion alongside a severe headache can indicate bleeding on the brain.
    {"confusion", "headache"},
]

URGENT_CARE_COMBOS = [
    {"fever", "cough"},
    {"nausea", "dizziness"},
    {"fever", "headache"},
    {"fever", "sore_throat"},
    {"fever", "abdominal_pain"},
    {"fever", "diarrhea"},
    {"fever", "rash"},
    {"abdominal_pain", "nausea"},
    {"diarrhea", "nausea"},
    # Dehydration risk, particularly in children and older adults.
    {"diarrhea", "dizziness"},
]

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


def assess_urgency(symptoms: List[str]) -> Dict[str, str]:
    """Map a set of symptoms to an urgency level.

    Checked most severe first, so the highest applicable level always wins.
    """
    symptom_set = set(symptoms)

    if symptom_set & EMERGENCY_SINGLE:
        return {"level": "emergency", "message": MESSAGES["emergency"]}

    for combo in EMERGENCY_COMBOS:
        if combo.issubset(symptom_set):
            return {"level": "emergency", "message": MESSAGES["emergency"]}

    for combo in URGENT_CARE_COMBOS:
        if combo.issubset(symptom_set):
            return {"level": "urgent_care", "message": MESSAGES["urgent_care"]}

    if symptom_set:
        return {"level": "self_care", "message": MESSAGES["self_care"]}

    return {"level": "unknown", "message": MESSAGES["unknown"]}
