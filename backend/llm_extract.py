"""Gemini-based symptom extraction, with the offline spaCy path as fallback.

The LLM only converts free text into a symptom list. It never decides urgency —
that stays in knowledge_graph.py so the triage decision remains deterministic
and testable.
"""

import json
import logging
import os
from typing import List, Optional

from dotenv import load_dotenv

from nlp_utils import SYMPTOM_PHRASES

load_dotenv()

log = logging.getLogger(__name__)

MODEL = "gemini-2.0-flash"

# Constrain output to the symptoms knowledge_graph.py actually has rules for.
# An invented symptom would just fall through to self_care, which hides the gap.
KNOWN_SYMPTOMS = sorted(SYMPTOM_PHRASES.keys())

PROMPT = """You extract symptoms from a patient's description for a triage system.

Return ONLY symptoms the patient currently reports having.
Do NOT include a symptom the patient denies (e.g. "no fever" means no fever).
Do NOT guess or infer symptoms that were not mentioned.

Allowed symptom values (use these exact strings, nothing else):
{allowed}

Patient description:
{text}
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "symptoms": {
            "type": "array",
            "items": {"type": "string", "enum": KNOWN_SYMPTOMS},
        }
    },
    "required": ["symptoms"],
}

_client = None
_client_failed = False


def _get_client():
    """Build the Gemini client once. Returns None if no key is configured."""
    global _client, _client_failed

    if _client is not None or _client_failed:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        log.info("GEMINI_API_KEY not set — using offline extraction only.")
        _client_failed = True
        return None

    try:
        from google import genai

        _client = genai.Client(api_key=api_key)
    except Exception as exc:
        log.warning("Could not initialise Gemini client: %s", exc)
        _client_failed = True
        return None

    return _client


def is_enabled() -> bool:
    """True when a Gemini client is available."""
    return _get_client() is not None


def extract_symptoms_llm(text: str, timeout_seconds: float = 8.0) -> Optional[List[str]]:
    """Extract symptoms via Gemini.

    Returns None on any failure (no key, rate limit, network error, bad
    response) so the caller can fall back to offline extraction. This function
    must never raise — a triage request should not fail because the LLM did.
    """
    client = _get_client()
    if client is None or not text or not text.strip():
        return None

    try:
        from google.genai import types

        response = client.models.generate_content(
            model=MODEL,
            contents=PROMPT.format(allowed=", ".join(KNOWN_SYMPTOMS), text=text),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
            ),
        )
    except Exception as exc:
        # Rate limits, network failures, quota exhaustion all land here.
        log.warning("Gemini extraction failed, falling back to offline: %s", exc)
        return None

    raw = (response.text or "").strip()
    if not raw:
        return None

    try:
        symptoms = json.loads(raw).get("symptoms", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        log.warning("Could not parse Gemini response %r: %s", raw[:200], exc)
        return None

    # Defend against anything outside the allowed set slipping through the
    # schema — knowledge_graph.py has no rules for unknown symptom names.
    cleaned = {s for s in symptoms if isinstance(s, str) and s in KNOWN_SYMPTOMS}
    return sorted(cleaned)
