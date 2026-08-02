from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import context as patient_context
import doctors as doctor_directory
import hours
import i18n
import specialties as specialty_routing
import symptoms as symptom_data
from nlp_utils import extract_symptoms
from knowledge_graph import MESSAGES, REASON_TEMPLATES, assess_urgency
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
    # Both optional. Age and duration make the answer better, but requiring them
    # would put a form between a frightened person and an emergency number.
    age: Optional[int] = None
    duration: Optional[str] = None
    lang: Optional[str] = None


# --- Localisation helpers ---------------------------------------------------
# English is produced by the modules that own it and translated here on the way
# out, so no rule module has to know that other languages exist.


def _symptom_details(symptom_ids, lang):
    details = []
    for symptom_id in symptom_ids:
        text = i18n.symptom_text(symptom_id, lang)
        symptom = symptom_data.BY_ID.get(symptom_id)
        details.append(
            {
                "id": symptom_id,
                "label": text["label"],
                "description": text["description"],
                "system": symptom.system if symptom else "general",
            }
        )
    return details


def _contacts(level, lang):
    localised = []
    for contact in get_contacts(level):
        name, note = i18n.contact_text(
            contact["number"], lang, contact["name"], contact["note"]
        )
        localised.append({"name": name, "number": contact["number"], "note": note})
    return localised


def _crisis_contacts(lang):
    localised = []
    for contact in CRISIS_CONTACTS:
        name, note = i18n.contact_text(
            contact["number"], lang, contact["name"], contact["note"]
        )
        localised.append({"name": name, "number": contact["number"], "note": note})
    return localised


def _specialties(symptom_ids, level, lang):
    localised = []
    for specialty in specialty_routing.recommend(symptom_ids, level):
        name, focus = i18n.specialty_text(
            specialty["id"], lang, specialty["name"], specialty["focus"]
        )
        localised.append(
            {
                "id": specialty["id"],
                "name": name,
                "focus": focus,
                "icon": specialty["icon"],
            }
        )
    return localised


def _reason(result, lang):
    """Translate a rule explanation, including the two templated ones.

    The templates name specific symptoms, so their labels have to be translated
    as well -- otherwise a Bengali sentence ends with an English symptom list.
    """
    key = result.get("reason_key", "")
    english = result.get("reason", "")
    if not key:
        return english

    named = result.get("reason_symptoms") or []
    if named:
        labels = ", ".join(
            i18n.symptom_text(s, lang)["label"].lower() for s in named
        )
        template = i18n.reason(key, lang, REASON_TEMPLATES[key])
        return template.format(names=labels)

    return i18n.reason(key, lang, english)


def _context_notes(notes, lang):
    """Join each escalation prefix to its explanation in the target language."""
    rendered = []
    for note in notes:
        body = i18n.simple(note["key"], lang, note["text"])
        if note.get("params"):
            body = body.format(**note["params"])

        raised = note.get("raised")
        if raised == "emergency":
            prefix = i18n.simple("raised_emergency", lang, "Raised to emergency.")
        elif raised == "one_level":
            prefix = i18n.simple("raised_one_level", lang, "Raised one level.")
        else:
            prefix = ""

        rendered.append(f"{prefix} {body}".strip())
    return rendered


@app.post("/triage")
def triage(request: TriageRequest):
    text = request.message
    lang = i18n.normalise(request.lang)

    # 1. Crisis check runs first and short-circuits everything. Someone saying
    #    they want to hurt themselves needs a counsellor now, and should not
    #    have that buried under a symptom analysis.
    if check_crisis(text):
        return {
            "symptoms_detected": [],
            "symptom_details": [],
            "urgency_level": "crisis",
            "message": i18n.simple("crisis_message", lang, CRISIS_MESSAGE),
            "reason": "",
            "extraction_source": "safety_override",
            "contacts": _crisis_contacts(lang),
            "recommended_specialties": _specialties([], "crisis", lang),
            "disclaimer": i18n.simple("disclaimer", lang, DISCLAIMER),
            "safety_note": None,
            "context_notes": [],
            "lang": lang,
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
    reason = _reason(result, lang)
    safety_note = None

    # 3. Plain-language emergencies ("collapsed", "not breathing") override the
    #    symptom vocabulary entirely. Without this, wording outside the known
    #    symptoms grades as "unknown" — the app shrugging at a real emergency.
    override = check_emergency_override(text)
    if override:
        level = "emergency"
        # The rule-based reason described the *un-escalated* grade, so it now
        # contradicts the verdict — "should be seen today" sitting under an
        # emergency result. safety_note explains the escalation instead.
        reason = ""
        safety_note = i18n.simple(
            "safety_escalated_emergency",
            lang,
            f"Escalated to emergency: description mentions "
            f"{override.replace('_', ' ')}.",
        )

    # 4. Severity language moves the result up one level. "Worst headache of my
    #    life" is a recognised red flag rather than an ordinary headache.
    #    Skipped when already emergency, and when nothing at all was detected —
    #    "severe" with no symptom and no danger phrase is too thin to act on.
    elif has_severity_marker(text) and symptoms:
        escalated = escalate(level)
        if escalated != level:
            level = escalated
            reason = ""
            safety_note = i18n.simple(
                "safety_escalated_severe",
                lang,
                "Escalated one level: symptoms described as severe.",
            )

    # 5. Age and duration. Applied last so they refine whatever the earlier
    #    layers concluded, and they can only ever raise the level — a wrong age
    #    makes the app more cautious, never less.
    age = patient_context.parse_age(request.age)
    duration = patient_context.normalise_duration(request.duration)
    level_before_context = level
    level, context_notes = patient_context.apply(level, symptoms, age, duration)
    if level != level_before_context:
        # Same trap as the safety overrides: the rule's own explanation described
        # the grade before the escalation, so leaving it in place puts "should be
        # seen today" underneath "go now". The context note explains it instead.
        reason = ""

    return {
        "symptoms_detected": symptoms,
        # Labels and plain-language descriptions, so the UI never has to show a
        # raw identifier like "one_sided_weakness" to a frightened person.
        "symptom_details": _symptom_details(symptoms, lang),
        "urgency_level": level,
        "message": i18n.message(level, lang, MESSAGES[level]),
        "reason": reason,
        "extraction_source": source,
        "contacts": _contacts(level, lang),
        "recommended_specialties": _specialties(symptoms, level, lang),
        "disclaimer": i18n.simple("disclaimer", lang, DISCLAIMER),
        "safety_note": safety_note,
        "context_notes": _context_notes(context_notes, lang),
        "lang": lang,
    }


@app.get("/languages")
def list_languages(lang: Optional[str] = None):
    """Available languages, and every interface string for the requested one.

    The frontend holds no English text of its own: it asks for the strings and
    renders whatever comes back. That means adding a language is a backend-only
    change, and a half-finished translation shows English for the missing keys
    rather than blank space.
    """
    chosen = i18n.normalise(lang)
    return {
        "languages": i18n.LANGUAGES,
        "current": chosen,
        "strings": i18n.ui(chosen),
    }


@app.get("/symptoms")
def list_symptoms(lang: Optional[str] = None):
    """The full recognisable vocabulary, grouped by body system.

    Powers the frontend's symptom reference. Being able to see what the app can
    and cannot recognise is the honest alternative to letting people guess.
    """
    chosen = i18n.normalise(lang)

    systems = []
    for group in symptom_data.grouped_by_system():
        translated = [
            {
                "id": s["id"],
                "label": i18n.symptom_text(s["id"], chosen)["label"],
                "description": i18n.symptom_text(s["id"], chosen)["description"],
                "weight": s["weight"],
            }
            for s in group["symptoms"]
        ]
        # Re-sort after translating: alphabetical order in English is meaningless
        # once the labels are in Devanagari or Bengali script.
        translated.sort(key=lambda s: s["label"])
        systems.append(
            {
                "id": group["id"],
                "label": i18n.system_label(group["id"], chosen),
                "symptoms": translated,
            }
        )

    return {
        "systems": systems,
        "total": len(symptom_data.ALL_IDS),
        # The duration choices ride along here rather than on their own endpoint:
        # the frontend already fetches this at startup, and the durations are
        # part of the same "what can this app understand" vocabulary.
        "durations": [
            {
                "id": option["id"],
                "label": i18n.duration_label(option["id"], chosen, option["label"]),
            }
            for option in patient_context.options()
        ],
        "lang": chosen,
    }


@app.get("/specialties")
def list_specialties(lang: Optional[str] = None):
    """Every specialty, with how many doctors are listed for each."""
    chosen = i18n.normalise(lang)

    localised = []
    for specialty in specialty_routing.all_specialties():
        name, focus = i18n.specialty_text(
            specialty["id"], chosen, specialty["name"], specialty["focus"]
        )
        localised.append(
            {
                "id": specialty["id"],
                "name": name,
                "focus": focus,
                "icon": specialty["icon"],
            }
        )

    return {
        "specialties": localised,
        "counts": doctor_directory.counts_by_specialty(),
        "systems": specialty_routing.systems_with_specialties(),
        "lang": chosen,
    }


@app.get("/doctors")
def list_doctors(specialty: Optional[str] = None, lang: Optional[str] = None):
    """The doctor directory, optionally filtered to one specialty.

    `using_placeholders` tells the frontend to show a warning banner. It is part
    of the response rather than a frontend constant so the banner disappears on
    its own the moment real contacts are added to doctors.json.
    """
    if specialty is not None:
        if specialty not in specialty_routing.SPECIALTIES:
            raise HTTPException(
                status_code=404, detail=f"Unknown specialty: {specialty}"
            )
        listed = doctor_directory.for_specialty(specialty)
    else:
        listed = doctor_directory.all_doctors()

    # Open/closed is computed here rather than in the browser because the rules
    # (split shifts, next-opening lookahead) are worth having tests around.
    # Distance deliberately is not: it needs the patient's coordinates, and those
    # should never leave their device for a health app.
    now = datetime.now()
    listed = [
        {**doctor, "availability": hours.status(doctor.get("hours"), now)}
        for doctor in listed
    ]

    return {
        "doctors": listed,
        "using_placeholders": doctor_directory.using_placeholders(),
        # Doctor names, hospitals and timings are not translated: they are proper
        # nouns and free text a user typed into doctors.json, and machine
        # -translating a hospital's name is how someone ends up at the wrong one.
        "disclaimer": i18n.simple("disclaimer", i18n.normalise(lang), DISCLAIMER),
    }


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "llm_enabled": is_enabled(),
        "symptoms_known": len(symptom_data.ALL_IDS),
        "doctors_listed": len(doctor_directory.DOCTORS),
        "doctors_are_placeholders": doctor_directory.using_placeholders(),
    }
