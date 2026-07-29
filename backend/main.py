from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nlp_utils import extract_symptoms
from knowledge_graph import assess_urgency
from llm_extract import extract_symptoms_llm, is_enabled

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
    # Try the LLM first — it handles messy phrasing the keyword matcher can't.
    # It returns None on any failure (no key, rate limit, network down), so the
    # offline spaCy path keeps the endpoint working regardless.
    symptoms = extract_symptoms_llm(request.message)
    source = "llm"

    if symptoms is None:
        symptoms = extract_symptoms(request.message)
        source = "offline"

    result = assess_urgency(symptoms)
    return {
        "symptoms_detected": symptoms,
        "urgency_level": result["level"],
        "message": result["message"],
        "extraction_source": source,
    }


@app.get("/")
def health_check():
    return {"status": "ok", "llm_enabled": is_enabled()}
