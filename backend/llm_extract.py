"""Gemini-based symptom extraction, with the offline spaCy path as fallback.

The LLM only converts free text into a symptom list. It never decides urgency —
that stays in knowledge_graph.py so the triage decision remains deterministic
and testable.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import List, Optional

from dotenv import load_dotenv

from symptoms import ALL_IDS, BY_ID

# Anchored to this file rather than the working directory. A bare load_dotenv()
# searches upward from wherever the process was started, so running
# `uvicorn main:app --app-dir backend` from the project root -- the natural way
# to start it, and what the VS Code instructions use -- silently failed to find
# backend/.env and disabled the LLM path with only an INFO log to show for it.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

log = logging.getLogger(__name__)

# Alias that tracks the current Flash model. Pinned versions like
# gemini-2.0-flash return "limit: 0" (no free-tier quota) or 404 for newly
# created API keys, so prefer the alias.
MODEL = "gemini-flash-latest"

# Constrain output to the symptoms knowledge_graph.py actually has rules for.
# An invented symptom would just fall through to self_care, which hides the gap.
KNOWN_SYMPTOMS = ALL_IDS

# Each allowed value is listed with its description rather than bare. With 79
# symptoms the ids alone are ambiguous — "numbness" and "one_sided_weakness"
# overlap, and only the descriptions make the intended split clear.
ALLOWED_BLOCK = "\n".join(
    f"- {s.id}: {s.label} — {s.description}" for s in (BY_ID[i] for i in ALL_IDS)
)

PROMPT = """You extract symptoms from a patient's description for a triage system.

The description may be in English, Hindi or Bengali, in either the native script
or written in Latin letters ("bukhar hai", "matha byatha"). Understand whichever
is used and always answer with the English id strings below.

Return ONLY symptoms the patient currently reports having.
Do NOT include a symptom the patient denies (e.g. "no fever" means no fever).
Do NOT guess or infer symptoms that were not mentioned.
Prefer the most specific match: "coughing up blood" is coughing_blood, not cough.

Allowed symptom values (use these exact id strings, nothing else):
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

# --- Timeouts ---------------------------------------------------------------
# Two separate limits, because the API will not accept the one that matters.
#
# HTTP_DEADLINE_SECONDS is what Gemini is told, and it is pinned to the minimum
# the API allows: anything lower comes back "Manually set deadline 5s is too
# short. Minimum allowed deadline is 10s."
#
# WAIT_BUDGET_SECONDS is how long a triage request will actually wait before
# giving up and using the offline path. Ten seconds of blank screen is too long
# for an app whose answer might be "call an ambulance", and the offline
# extractor is good enough that waiting longer is a bad trade. Six seconds
# comfortably covers a healthy Gemini response (measured 2-4s) while cutting the
# worst case nearly in half.
HTTP_DEADLINE_SECONDS = 10.0
WAIT_BUDGET_SECONDS = 6.0

# Bounded on purpose. When the budget expires the HTTP request is still in
# flight -- it cannot be cancelled, only abandoned -- so its thread lingers until
# the 10s deadline fires. A bounded pool means a burst of slow requests cannot
# spawn unbounded threads; it just saturates, and a saturated pool makes
# submissions time out immediately and fall through to offline extraction, which
# is the correct way for this to degrade.
_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="gemini")

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


def extract_symptoms_llm(
    text: str, timeout_seconds: float = WAIT_BUDGET_SECONDS
) -> Optional[List[str]]:
    """Extract symptoms via Gemini, giving up after `timeout_seconds`.

    Returns None on any failure (no key, rate limit, network error, bad
    response, or simply taking too long) so the caller can fall back to offline
    extraction. This function must never raise — a triage request should not
    fail because the LLM did, or because it was slow.
    """
    if not text or not text.strip() or _get_client() is None:
        return None

    future = _EXECUTOR.submit(_call_gemini, text)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeout:
        # The request is still running and will stop on its own at the HTTP
        # deadline. Abandoning it is the point: the user gets the offline answer
        # now rather than a blank screen for another four seconds.
        log.warning(
            "Gemini did not answer within %.1fs, using offline extraction.",
            timeout_seconds,
        )
        return None
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Gemini extraction failed unexpectedly: %s", exc)
        return None


def _call_gemini(text: str) -> Optional[List[str]]:
    """The blocking API call. Runs on a worker thread; never raises."""
    client = _get_client()
    if client is None:
        return None

    try:
        from google.genai import types

        response = client.models.generate_content(
            model=MODEL,
            contents=PROMPT.format(allowed=ALLOWED_BLOCK, text=text),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                http_options=types.HttpOptions(
                    timeout=int(HTTP_DEADLINE_SECONDS * 1000)
                ),
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
