from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nlp_utils import extract_symptoms
from knowledge_graph import assess_urgency

app = FastAPI(title="Smmart Healthcare Triage Prototype")

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
    symptoms = extract_symptoms(request.message)
    result = assess_urgency(symptoms)
    return {
        "symptoms_detected": symptoms,
        "urgency_level": result["level"],
        "message": result["message"],
    }
@app.get("/")
def health_check():
    return {"status": "ok"}

