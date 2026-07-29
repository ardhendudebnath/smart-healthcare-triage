"""Emergency and health helpline contacts, keyed by urgency level.

⚠️  VERIFY BEFORE ANY REAL USE  ⚠️
These numbers are for India and were taken from the official sources listed
below in July 2026. Helpline numbers change, and some vary by state. A wrong
emergency number in a triage app is worse than no number at all -- confirm
against your state health department before this is used by anyone real.

Sources:
  112       National emergency number (police/fire/ambulance)
            https://112.gov.in  and  https://www.incredibleindia.gov.in/en/emergency
  102 / 108 Ambulance. NOTE: sources disagree -- the national tourism portal
            lists 102 as ambulance and 108 as disaster management, while other
            sources list 108 as the medical emergency line. Both are in use and
            the split varies by state, which is exactly why 112 is listed first.
  104       Medical helpline (advice, non-emergency)
            https://www.incredibleindia.gov.in/en/emergency
  14416     Tele-MANAS national mental health helpline (MoHFW)
            https://telemanas.mohfw.gov.in

To adapt this for another country, replace CONTACTS below. Nothing else in the
codebase hardcodes a phone number.
"""

from typing import Dict, List

REGION = "IN"

# Shown for every urgency level, including "unknown" -- someone whose symptoms
# we failed to parse still needs a way to reach help.
ALWAYS_AVAILABLE = [
    {
        "name": "National Emergency Number",
        "number": "112",
        "note": "Police, fire and ambulance. Works without SIM or network signal.",
    },
]

CONTACTS: Dict[str, List[Dict[str, str]]] = {
    "emergency": [
        {
            "name": "National Emergency Number",
            "number": "112",
            "note": "Call now. Works without SIM or network signal.",
        },
        {
            "name": "Ambulance",
            "number": "102 / 108",
            "note": "Ambulance line. Which number applies varies by state.",
        },
    ],
    "urgent_care": [
        {
            "name": "Medical Helpline",
            "number": "104",
            "note": "Free medical advice and guidance to a nearby facility.",
        },
        {
            "name": "National Emergency Number",
            "number": "112",
            "note": "Call this instead if symptoms get worse before you are seen.",
        },
    ],
    "self_care": [
        {
            "name": "Medical Helpline",
            "number": "104",
            "note": "Free medical advice if you are unsure whether to see a doctor.",
        },
    ],
    "unknown": [
        {
            "name": "Medical Helpline",
            "number": "104",
            "note": "Speak to someone who can ask the right questions.",
        },
    ],
}

MENTAL_HEALTH = {
    "name": "Tele-MANAS (Mental Health)",
    "number": "14416",
    "note": "Free, confidential, 24/7. Available in 20+ languages.",
}

DISCLAIMER = (
    "This is an automated prototype, not medical advice and not a diagnosis. "
    "If you think this is an emergency, call 112 immediately rather than "
    "relying on this result."
)


def get_contacts(urgency_level: str) -> List[Dict[str, str]]:
    """Return the contacts to show for an urgency level.

    Falls back to the always-available list for an unrecognised level so a
    caller can never end up with no way to reach help.
    """
    return CONTACTS.get(urgency_level, ALWAYS_AVAILABLE)
