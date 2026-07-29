from typing import List, Dict
EMERGENCY_COMBOS = [
    {"chest_pain", "difficulty_breathing"},
    {"difficulty_breathing", "fever"},
]

URGENT_CARE_COMBOS = [
    {"fever", "cough"},
    {"nausea", "dizziness"},
]

def assess_urgency(symptoms: List[str]) -> Dict[str, str]:
    symptom_set = set(symptoms)

    for combo in EMERGENCY_COMBOS:
        if combo.issubset(symptom_set):
            return{"level": "emergency",
                   "message": "These symptoms can indicate a serious condition. Please go to the emergency room or call emergency service now."}

    for combo in URGENT_CARE_COMBOS:
        if combo.issubset(symptom_set):
            return {"level": "urgent_care",
                    "message": "These symptoms should be seen the same day. Please visit an urgent care clinic."}

    if len(symptom_set) >= 1:
        return {"level": "self_care",
                "message": "These symptoms are best checked by your regular doctor. Book a routine appointment "
                }
    return {"level": "unknown",
            "message": "I couldn't identify clear symptoms. Could you describe how you're feeling in more detail?"}
        