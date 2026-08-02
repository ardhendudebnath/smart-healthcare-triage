"""Safety overrides that run before and after normal symptom triage.

Symptom extraction maps text onto a fixed vocabulary. Anything outside that
vocabulary comes back empty, which means a description like "he collapsed and
is not responding" would otherwise be graded "unknown" -- the app shrugging at
a genuine emergency. These checks catch danger stated in plain language,
independently of the symptom list.

Design rule, consistent with knowledge_graph.py: escalate when uncertain.
Matching here is deliberately loose. A false positive shows someone an
emergency number they did not need; a false negative tells someone in danger
that nothing is wrong. Those costs are not equal.
"""

import re
from typing import List, Optional

from phrases_indic import check_crisis_indic, check_emergency_indic

# Phrases that mean "emergency" regardless of which symptoms were extracted.
# Grouped only for readability -- any match escalates the same way.
EMERGENCY_OVERRIDE_PHRASES = {
    "unresponsive": [
        "not responding",
        "unresponsive",
        "unconscious",
        "passed out",
        "collapsed",
        "blacked out",
        "will not wake",
        "wont wake",
        "not waking up",
    ],
    "not_breathing": [
        "not breathing",
        "stopped breathing",
        "cant breathe at all",
        "choking",
        "turning blue",
    ],
    "cardiac_or_stroke": [
        "heart attack",
        "cardiac arrest",
        "having a stroke",
    ],
    "seizure": [
        "seizure",
        "convulsion",
        "fitting",
    ],
    "severe_bleeding": [
        "bleeding heavily",
        "heavy bleeding",
        "lot of blood",
        "losing blood",
        "wont stop bleeding",
        "will not stop bleeding",
    ],
    "poisoning": [
        "overdose",
        "poisoned",
        "swallowed poison",
        "took too many pills",
    ],
}

# Handled separately from medical emergencies: the right response is a crisis
# counsellor, not an ambulance dispatcher.
CRISIS_PHRASES = [
    "kill myself",
    "killing myself",
    "end my life",
    "ending my life",
    "want to die",
    "suicidal",
    "suicide",
    "harm myself",
    "hurt myself",
    "self harm",
]

# Intensity language. On its own this is not an emergency, but paired with a
# real symptom it is a reason to move up one level -- "worst headache of my
# life" is a recognised red flag, not an ordinary headache.
SEVERITY_PHRASES = [
    "severe",
    "severely",
    "worst",
    "unbearable",
    "excruciating",
    "extreme",
    "extremely",
    "agony",
    "cant bear",
    "can not bear",
    "cannot bear",
    "10/10",
]

# Ordered least to most urgent, so escalation is just an index step.
ESCALATION_ORDER = ["unknown", "self_care", "urgent_care", "emergency"]


def _normalise(text: str) -> str:
    """Lowercase and collapse punctuation so "can't" matches "cant"."""
    lowered = text.lower()
    lowered = lowered.replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", lowered)


def _contains_any(text: str, phrases: List[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def check_emergency_override(text: str) -> Optional[str]:
    """Return the category name if the text describes an obvious emergency.

    Checks Hindi and Bengali as well as English. These overrides are the last
    line before someone in danger is told nothing is wrong, so they cannot be
    English-only in an app aimed at Indian users.
    """
    if not text:
        return None
    normalised = _normalise(text)
    for category, phrases in EMERGENCY_OVERRIDE_PHRASES.items():
        if _contains_any(normalised, phrases):
            return category
    return check_emergency_indic(text)


def check_crisis(text: str) -> bool:
    """True if the text mentions suicide or self-harm, in any supported language.

    The most important thing in this module to get right in every language: a
    person writing about self-harm in Bengali needs the counselling line just as
    much as one writing in English.
    """
    if not text:
        return False
    if _contains_any(_normalise(text), CRISIS_PHRASES):
        return True
    return check_crisis_indic(text)


def has_severity_marker(text: str) -> bool:
    """True if the text describes symptoms as severe or extreme."""
    if not text:
        return False
    return _contains_any(_normalise(text), SEVERITY_PHRASES)


def escalate(level: str) -> str:
    """Move one step up the urgency scale.

    "unknown" is deliberately skipped straight to self_care rather than being
    treated as the bottom of a scale -- it means "we could not tell", not
    "nothing is wrong".
    """
    try:
        index = ESCALATION_ORDER.index(level)
    except ValueError:
        return level
    return ESCALATION_ORDER[min(index + 1, len(ESCALATION_ORDER) - 1)]
