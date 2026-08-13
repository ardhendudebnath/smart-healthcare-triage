"""Version stamps, so any past result can be traced to the logic that produced it.

Why this exists
---------------
"The app said emergency" is not a reviewable statement. "Ruleset r4a91c2 with
vocabulary v7f3e01 said emergency, and here is that ruleset" is. Medical
software has to be able to answer the second question months later, after the
rules have changed several times, and a triage result that cannot be tied to
the logic behind it cannot be audited, reproduced, or defended.

Content hashes, not hand-written numbers
----------------------------------------
The ruleset and vocabulary versions are derived from the content itself rather
than typed in by hand. A hand-maintained version number is wrong the moment
someone edits a rule and forgets to bump it -- and it fails silently, which is
the worst way for a traceability mechanism to fail: the audit log keeps saying
v3 while v3 quietly means three different things.

Deriving the hash from the data means the version cannot drift from what it
describes. Change a rule and the stamp changes with it, whether or not anyone
remembered to.

APP_VERSION is hand-set because it means something different: it is the release
humans talk about, and is meant to be stable across a deploy that changed no
rules.
"""

import hashlib
import json
from typing import Dict

from knowledge_graph import (
    EMERGENCY_COMBOS,
    EMERGENCY_SINGLE,
    URGENT_CARE_COMBOS,
)
from symptoms import SYMPTOM_PHRASES

# Semantic version of the application as a whole. Bump by hand on release.
APP_VERSION = "0.5.0"

# How many hex characters of each content hash to keep. Twelve is far more than
# enough to be collision-free for a rule table this size, and short enough to
# read aloud over a phone call to whoever is investigating a result.
_HASH_LENGTH = 12


def _stable_hash(payload) -> str:
    """A hash that depends on content only, never on ordering or memory layout.

    Sets and dicts have no reliable iteration order between processes, so
    hashing their repr would produce a version that changes when nothing did --
    the other silent failure mode this module exists to avoid. Everything is
    sorted into a canonical form first.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:_HASH_LENGTH]


def _canonical_combos(combos) -> list:
    """Combo rules in a stable, JSON-serialisable shape.

    Each entry is (symptoms, rule_id, explanation). All three are included
    rather than just the grading part: an edited explanation changes what the
    patient was told, and an audit that cannot see that change is incomplete.
    """
    return sorted(
        [sorted(symptoms), rule_id, explanation]
        for symptoms, rule_id, explanation in combos
    )


def _ruleset_version() -> str:
    """Identifies the urgency rules that graded a result."""
    return _stable_hash(
        {
            "emergency_single": sorted(EMERGENCY_SINGLE),
            "emergency_combos": _canonical_combos(EMERGENCY_COMBOS),
            "urgent_care_combos": _canonical_combos(URGENT_CARE_COMBOS),
        }
    )


def _vocabulary_version() -> str:
    """Identifies the symptom vocabulary that read the patient's words.

    Separate from the ruleset on purpose. Adding a phrase changes what the app
    understands without changing how it grades, and an investigation needs to
    tell those two apart -- "we started recognising this phrase last month" and
    "we changed how we grade it last month" have different consequences.
    """
    return _stable_hash(
        {symptom: sorted(phrases) for symptom, phrases in SYMPTOM_PHRASES.items()}
    )


RULESET_VERSION = _ruleset_version()
VOCABULARY_VERSION = _vocabulary_version()


def stamp() -> Dict[str, str]:
    """The version block attached to every triage result and audit record."""
    return {
        "app": APP_VERSION,
        "ruleset": RULESET_VERSION,
        "vocabulary": VOCABULARY_VERSION,
    }


def describe() -> Dict:
    """Fuller detail for the /version endpoint and for support conversations."""
    return {
        **stamp(),
        "symptom_count": len(SYMPTOM_PHRASES),
        "phrase_count": sum(len(p) for p in SYMPTOM_PHRASES.values()),
        "emergency_single_count": len(EMERGENCY_SINGLE),
        "emergency_combo_count": len(EMERGENCY_COMBOS),
        "urgent_care_combo_count": len(URGENT_CARE_COMBOS),
    }
