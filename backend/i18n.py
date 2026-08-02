"""Language support: English, Hindi and Bengali.

⚠️  TRANSLATIONS NEED A NATIVE-SPEAKER REVIEW BEFORE REAL USE  ⚠️
The Hindi and Bengali strings in translations_hi.py and translations_bn.py were
produced without review by a native speaker or a clinician. In a triage app a
mistranslation is the same class of problem as a wrong phone number: someone
acts on it. Treat them as a working draft. The English text remains the
authoritative version of every safety-critical message.

How this fits together
----------------------
English lives in the modules that own it -- symptoms.py, knowledge_graph.py,
contacts.py -- and stays the single source of truth. This module only carries
the other two languages, keyed by the same identifiers, and falls back to
English for anything missing. That means a half-finished translation degrades to
English rather than to a blank screen, and adding a symptom never breaks a
language.

Input vs output
---------------
These tables translate what the app *says*. What the user *writes* is handled
separately: the Gemini path reads Hindi and Bengali natively, and nlp_utils.py
carries a small Devanagari/Bengali phrase table so that red-flag symptoms are
still recognised when the LLM is unavailable. Offline coverage in those two
languages is limited to the red flags on purpose -- see nlp_utils.py.
"""

from typing import Dict, List, Optional

import translations_bn
import translations_hi
from symptoms import BY_ID, SYSTEMS

DEFAULT_LANGUAGE = "en"

LANGUAGES: List[Dict[str, str]] = [
    {"id": "en", "label": "English", "native": "English"},
    {"id": "hi", "label": "Hindi", "native": "हिन्दी"},
    {"id": "bn", "label": "Bengali", "native": "বাংলা"},
]

LANGUAGE_IDS = {language["id"] for language in LANGUAGES}

# Everything except English. English is never looked up here -- it is read from
# the module that owns it.
_TABLES = {
    "hi": translations_hi,
    "bn": translations_bn,
}


def normalise(lang: Optional[str]) -> str:
    """A supported language id, defaulting to English.

    Unknown values fall back rather than raising: a stale bookmark with
    ?lang=fr should show the app in English, not an error page.
    """
    if lang in LANGUAGE_IDS:
        return lang
    return DEFAULT_LANGUAGE


# The English interface strings, and the authoritative list of UI keys. A
# translation file is complete when it covers every key here; anything it misses
# falls through to English rather than disappearing.
UI_EN: Dict[str, str] = {
    # header and navigation
    "tagline": "Describe how you feel. Find out how urgently to act.",
    "prototype": "Prototype",
    "emergency_button": "Emergency 112",
    "tab_check": "Check symptoms",
    "tab_guide": "Symptom guide",
    "tab_doctors": "Find a doctor",
    "skip_link": "Skip to content",
    # symptom checker
    "field_what_wrong": "What is wrong?",
    "field_hint_write": (
        "Write it in your own words — whole sentences are fine. Include how bad "
        "it is and how long it has been going on."
    ),
    "placeholder_message": "e.g. I've had a fever since yesterday and now my neck is stiff",
    "examples_hint": "Or start from an example:",
    "field_age": "Age",
    "field_duration": "How long",
    "optional": "optional",
    "hint_age": "Babies and older adults are assessed differently.",
    "hint_duration": "How long it has been going on.",
    "duration_not_sure": "Not sure",
    "btn_check": "Check symptoms",
    "btn_checking": "Checking…",
    "btn_clear": "Clear",
    # result
    "result_understood": "What we understood",
    "result_contacts": "Who to contact now",
    "result_doctor": "Which kind of doctor",
    "btn_see_doctors": "See doctors for this →",
    "btn_print": "🖨 Save or print",
    "no_symptoms_recognised": "No specific symptoms were recognised in that description.",
    "print_stamp": (
        "Automated result from the Smart Healthcare Triage prototype. "
        "This is not a medical diagnosis."
    ),
    # levels
    "level_emergency": "Emergency",
    "level_urgent_care": "Urgent",
    "level_self_care": "Routine",
    "level_unknown": "Unclear",
    "level_crisis": "Support",
    # symptom guide
    "guide_title": "What this app can recognise",
    "guide_intro": (
        "Everything below is understood by name. If what you are feeling is not "
        "here, describe it in your own words anyway — plain descriptions of "
        "serious situations are recognised separately."
    ),
    "search_placeholder": "Search symptoms, e.g. chest, fever, sleep",
    "symptoms_recognised": "symptoms recognised",
    "symptoms_matching": "matching",
    "no_search_results": "No symptoms match that search.",
    "red_flag": "red flag",
    # doctor directory
    "doctors_title": "Find a doctor",
    "doctors_intro": (
        "Contact details for each speciality, with the assistant's number where "
        "one is listed."
    ),
    "placeholder_warning_title": "These are sample entries, not real doctors.",
    "placeholder_warning_body": (
        "The phone numbers do not work. Copy backend/doctors.example.json to "
        "backend/doctors.json and put real contacts in it — this warning "
        "disappears on its own once you do."
    ),
    "sample_entry": "Sample entry",
    "filter_all": "All",
    "doctor_hospital": "Hospital",
    "doctor_city": "City",
    "doctor_hours": "Hours",
    "doctor_speaks": "Speaks",
    "doctor_assistant": "Assistant",
    "btn_call": "☎ Call",
    "btn_whatsapp": "WhatsApp",
    "btn_whatsapp_result": "WhatsApp with my result",
    "btn_call_assistant": "Call assistant",
    "no_doctors": "No doctors listed for this speciality yet.",
    # location and availability
    "result_doctors": "Doctors you can contact",
    "btn_find_near_me": "📍 Find nearest",
    "btn_locating": "Locating…",
    "btn_see_all_doctors": "See all doctors →",
    "location_denied": "Location not shared — doctors are listed without distance.",
    "location_error": "Could not get your location — doctors are listed without distance.",
    "location_missing": "Location not listed",
    "sorted_open_nearest": "Open now first, then nearest.",
    "status_open_now": "Open now",
    "status_closed_now": "Closed",
    "status_always_open": "Open 24 hours",
    "status_hours_unknown": "Hours not listed",
    "until_label": "until {until}",
    "opens_label": "opens {opens}",
    "distance_km": "{distance} km away",
    "distance_m": "{distance} m away",
    # WhatsApp prefill
    "wa_greeting": "Hello, I would like to ask about an appointment.",
    "wa_symptoms": "Symptoms",
    "wa_duration": "Duration",
    "wa_age": "Age",
    "wa_result": "Automated triage result",
    "wa_footer": "(Sent from the Smart Healthcare Triage app — not a medical diagnosis.)",
    # errors and footer
    "error_server": (
        "Could not reach the triage server. If this is an emergency, call 112 "
        "now rather than waiting."
    ),
    "error_directory": "Could not load the directory — is the server running?",
    "error_symptoms": "Could not load the symptom list — is the server running?",
    "footer_note": (
        "Symptom rules are assembled from commonly published warning signs and "
        "have not been reviewed by a clinician. Helpline numbers are for India "
        "and should be verified against your state health department before "
        "real use."
    ),
    "language_label": "Language",
}


def ui(lang: str) -> Dict[str, str]:
    """The interface strings for a language, with English filled in for gaps."""
    strings = dict(UI_EN)
    table = _TABLES.get(normalise(lang))
    if table:
        strings.update({k: v for k, v in table.UI.items() if v})
    return strings


def symptom_text(symptom_id: str, lang: str) -> Dict[str, str]:
    """Label and description for one symptom in the requested language."""
    symptom = BY_ID.get(symptom_id)
    label = symptom.label if symptom else symptom_id.replace("_", " ").capitalize()
    description = symptom.description if symptom else ""

    table = _TABLES.get(normalise(lang))
    if table:
        translated = table.SYMPTOMS.get(symptom_id)
        if translated:
            label = translated.get("label") or label
            description = translated.get("description") or description

    return {"label": label, "description": description}


def system_label(system_id: str, lang: str) -> str:
    table = _TABLES.get(normalise(lang))
    if table:
        translated = table.SYSTEMS.get(system_id)
        if translated:
            return translated
    return SYSTEMS.get(system_id, system_id)


def message(level: str, lang: str, english: str) -> str:
    """An urgency message, falling back to the English passed in."""
    table = _TABLES.get(normalise(lang))
    if table:
        return table.MESSAGES.get(level) or english
    return english


def reason(key: str, lang: str, english: str) -> str:
    """A rule explanation, keyed so it survives translation.

    Rule reasons are generated in knowledge_graph.py, which knows nothing about
    languages. It emits a stable key alongside the English text; this looks the
    key up and hands back English when there is no translation.
    """
    if not key:
        return english
    table = _TABLES.get(normalise(lang))
    if table:
        return table.REASONS.get(key) or english
    return english


def specialty_text(specialty_id: str, lang: str, english_name: str, english_focus: str):
    table = _TABLES.get(normalise(lang))
    if table:
        translated = table.SPECIALTIES.get(specialty_id)
        if translated:
            return (
                translated.get("name") or english_name,
                translated.get("focus") or english_focus,
            )
    return english_name, english_focus


def contact_text(number: str, lang: str, english_name: str, english_note: str):
    """Helpline name and note. Keyed by the number, which never changes.

    Keying on the number rather than the name means a reworded English label
    cannot silently orphan its translations.
    """
    table = _TABLES.get(normalise(lang))
    if table:
        translated = table.CONTACTS.get(number)
        if translated:
            return (
                translated.get("name") or english_name,
                translated.get("note") or english_note,
            )
    return english_name, english_note


def duration_label(duration_id: str, lang: str, english: str) -> str:
    table = _TABLES.get(normalise(lang))
    if table:
        return table.DURATIONS.get(duration_id) or english
    return english


def simple(key: str, lang: str, english: str) -> str:
    """Any other standalone string: disclaimer, crisis message, safety notes."""
    table = _TABLES.get(normalise(lang))
    if table:
        return table.STRINGS.get(key) or english
    return english
