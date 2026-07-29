from typing import List

SYMPTOM_KEYWORDS = {
    "chest_pain": ["chest pain", "chest hurts", "pain in my chest"],
    "difficulty_breathing": ["difficulty breathing", "can't breathe", "cant breathe", "shortness of breath", "trouble breathing"],
    "fever": ["fever", "high temperature", "temperature"],
    "cough": ["cough", "coughing"],
    "nausea": ["nausea", "nauseous", "feel sick", "vomiting", "throwing up"],
    "dizziness": ["dizziness", "dizzy", "lightheaded"],
}


def extract_symptoms(text: str) -> List[str]:
    text = text.lower()
    found = []
    for symptom, phrases in SYMPTOM_KEYWORDS.items():
        if any(phrase in text for phrase in phrases):
            found.append(symptom)
    return found
