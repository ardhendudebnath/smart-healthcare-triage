from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nlp_utils import extract_symptoms
from knowledge_graph import MESSAGES, assess_urgency
from llm_extract import extract_symptoms_llm, is_enabled
from contacts import CRISIS_CONTACTS, CRISIS_MESSAGE, DISCLAIMER, get_contacts
from safety import (
    check_crisis,
    check_emergency_override,
    escalate,
    has_severity_marker,
)

app = FastAPI(title="Smart Healthcare Triage Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriageRequest(BaseModel):
    message: str


@app.post("/triage")
def triage(request: TriageRequest):
    text = request.message

    # 1. Crisis check runs first and short-circuits everything. Someone saying
    #    they want to hurt themselves needs a counsellor now, and should not
    #    have that buried under a symptom analysis.
    if check_crisis(text):
        return {
            "symptoms_detected": [],
            "urgency_level": "crisis",
            "message": CRISIS_MESSAGE,
            "extraction_source": "safety_override",
            "contacts": CRISIS_CONTACTS,
            "disclaimer": DISCLAIMER,
        }

    # 2. Extract symptoms. LLM first for messy phrasing; it returns None on any
    #    failure (no key, rate limit, network down) so the offline spaCy path
    #    keeps the endpoint working regardless.
    symptoms = extract_symptoms_llm(text)
    source = "llm"
    if symptoms is None:
        symptoms = extract_symptoms(text)
        source = "offline"

    result = assess_urgency(symptoms)
    level = result["level"]
    message = result["message"]
    safety_note = None

    # 3. Plain-language emergencies ("collapsed", "not breathing") override the
    #    symptom vocabulary entirely. Without this, wording outside the 16
    #    known symptoms grades as "unknown" — the app shrugging at a real
    #    emergency.
    override = check_emergency_override(text)
    if override:
        level = "emergency"
        message = MESSAGES["emergency"]
        safety_note = f"Escalated to emergency: description mentions {override.replace('_', ' ')}."

    # 4. Severity language moves the result up one level. "Worst headache of my
    #    life" is a recognised red flag rather than an ordinary headache.
    #    Skipped when already emergency, and when nothing at all was detected —
    #    "severe" with no symptom and no danger phrase is too thin to act on.
    elif has_severity_marker(text) and symptoms:
        escalated = escalate(level)
        if escalated != level:
            level = escalated
            message = MESSAGES[level]
            safety_note = "Escalated one level: symptoms described as severe."

    return {
        "symptoms_detected": symptoms,
        "urgency_level": level,
        "message": message,
        "extraction_source": source,
        "contacts": get_contacts(level),
        "disclaimer": DISCLAIMER,
        "safety_note": safety_note,
    }


@app.get("/")
def health_check():
    return {"status": "ok", "llm_enabled": is_enabled()}
