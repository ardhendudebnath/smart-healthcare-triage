"""Which kind of doctor a set of symptoms points to.

Triage answers "how urgently"; this answers "who". They are separate questions
and separate modules: knowing you need care today does not tell you whether to
look for a cardiologist or an orthopaedic surgeon.

Routing is by body system, which is why the system names in symptoms.py are
load-bearing. A handful of symptoms need overriding because the body part
involved and the specialist who treats it do not line up -- swollen ankles are
a leg complaint that a cardiologist should see.

Names are written the way an Indian patient would encounter them, with the plain
meaning alongside: "ENT Specialist (ear, nose and throat)" is more useful than
"Otorhinolaryngologist".
"""

from dataclasses import dataclass
from typing import Dict, List

from symptoms import BY_ID, SYSTEMS, weight_of


@dataclass(frozen=True)
class Specialty:
    id: str
    name: str
    focus: str
    icon: str


SPECIALTIES: Dict[str, Specialty] = {
    "emergency_medicine": Specialty(
        id="emergency_medicine",
        name="Emergency Medicine",
        focus="Immediate, life-threatening problems",
        icon="🚑",
    ),
    "general_medicine": Specialty(
        id="general_medicine",
        name="General Physician",
        focus="First point of contact for most problems",
        icon="🩺",
    ),
    "cardiology": Specialty(
        id="cardiology",
        name="Cardiologist",
        focus="Heart and blood vessels",
        icon="❤️",
    ),
    "pulmonology": Specialty(
        id="pulmonology",
        name="Pulmonologist (Chest Specialist)",
        focus="Lungs and breathing",
        icon="🫁",
    ),
    "neurology": Specialty(
        id="neurology",
        name="Neurologist",
        focus="Brain, spine and nerves",
        icon="🧠",
    ),
    "gastroenterology": Specialty(
        id="gastroenterology",
        name="Gastroenterologist",
        focus="Stomach, liver and digestion",
        icon="🍽️",
    ),
    "urology": Specialty(
        id="urology",
        name="Urologist",
        focus="Kidneys, bladder and urinary tract",
        icon="💧",
    ),
    "orthopaedics": Specialty(
        id="orthopaedics",
        name="Orthopaedic Surgeon",
        focus="Bones, joints and muscles",
        icon="🦴",
    ),
    "ent": Specialty(
        id="ent",
        name="ENT Specialist",
        focus="Ear, nose and throat",
        icon="👂",
    ),
    "ophthalmology": Specialty(
        id="ophthalmology",
        name="Eye Specialist",
        focus="Eyes and vision",
        icon="👁️",
    ),
    "dentistry": Specialty(
        id="dentistry",
        name="Dentist",
        focus="Teeth and gums",
        icon="🦷",
    ),
    "dermatology": Specialty(
        id="dermatology",
        name="Dermatologist",
        focus="Skin, hair and nails",
        icon="🧬",
    ),
    "psychiatry": Specialty(
        id="psychiatry",
        name="Psychiatrist / Counsellor",
        focus="Mental health and emotional wellbeing",
        icon="💬",
    ),
    "gynaecology": Specialty(
        id="gynaecology",
        name="Gynaecologist / Obstetrician",
        focus="Women's health and pregnancy",
        icon="🤰",
    ),
    "paediatrics": Specialty(
        id="paediatrics",
        name="Paediatrician",
        focus="Babies and children",
        icon="👶",
    ),
}

# Default route: one specialty per body system.
SYSTEM_TO_SPECIALTY: Dict[str, str] = {
    "cardiac": "cardiology",
    "respiratory": "pulmonology",
    "neurological": "neurology",
    "digestive": "gastroenterology",
    "urinary": "urology",
    "musculoskeletal": "orthopaedics",
    "ent": "ent",
    "eye": "ophthalmology",
    "dental": "dentistry",
    "skin": "dermatology",
    "general": "general_medicine",
    "mental_health": "psychiatry",
    "womens_health": "gynaecology",
    "child": "paediatrics",
}

# Symptoms whose specialty differs from their body system's default.
SYMPTOM_OVERRIDES: Dict[str, str] = {
    # A cut or burn is skin, but it is a wound that needs dressing, not a
    # dermatology referral.
    "wound": "general_medicine",
    "burn": "emergency_medicine",
    # A sore throat is technically ENT, but nobody needs a specialist for one --
    # a general physician handles it.
    "sore_throat": "general_medicine",
    # These two cannot wait for an outpatient appointment at all.
    "allergic_reaction": "emergency_medicine",
    "injury_fracture": "emergency_medicine",
}

# How many specialties to suggest. More than three stops being a recommendation
# and starts being a list.
MAX_SUGGESTIONS = 3


def specialty_for(symptom_id: str) -> str:
    """The specialty that treats a given symptom."""
    if symptom_id in SYMPTOM_OVERRIDES:
        return SYMPTOM_OVERRIDES[symptom_id]
    symptom = BY_ID.get(symptom_id)
    if symptom is None:
        return "general_medicine"
    return SYSTEM_TO_SPECIALTY.get(symptom.system, "general_medicine")


def recommend(symptoms: List[str], urgency_level: str) -> List[Dict[str, str]]:
    """Suggest which doctors to contact, most relevant first.

    Emergency results always lead with emergency medicine -- the specialist
    matters less than being seen, and sending someone to book a cardiology
    appointment during a heart attack would be actively harmful. The organ
    specialty still follows, because it is what they will need afterwards.

    A crisis result returns only mental health: someone in that situation should
    not be handed a list of options to pick from.
    """
    if urgency_level == "crisis":
        return [_as_dict("psychiatry")]

    # Rank by how much severity each specialty accounts for, so the most serious
    # symptom decides who is listed first.
    scores: Dict[str, int] = {}
    for symptom_id in symptoms:
        specialty_id = specialty_for(symptom_id)
        scores[specialty_id] = scores.get(specialty_id, 0) + weight_of(symptom_id)

    ranked = sorted(scores, key=lambda s: (-scores[s], s))

    if urgency_level == "emergency":
        ranked = ["emergency_medicine"] + [
            s for s in ranked if s != "emergency_medicine"
        ]
    elif not ranked:
        # Nothing recognised, but the person still needs somewhere to start.
        ranked = ["general_medicine"]

    return [_as_dict(s) for s in ranked[:MAX_SUGGESTIONS] if s in SPECIALTIES]


def _as_dict(specialty_id: str) -> Dict[str, str]:
    specialty = SPECIALTIES[specialty_id]
    return {
        "id": specialty.id,
        "name": specialty.name,
        "focus": specialty.focus,
        "icon": specialty.icon,
    }


def all_specialties() -> List[Dict[str, str]]:
    """Every specialty, for the frontend's directory filters."""
    return [_as_dict(s) for s in SPECIALTIES]


def systems_with_specialties() -> List[Dict[str, str]]:
    """Body system → specialty, so the UI can explain the mapping."""
    return [
        {
            "system": system_id,
            "system_label": system_label,
            "specialty": SYSTEM_TO_SPECIALTY.get(system_id, "general_medicine"),
        }
        for system_id, system_label in SYSTEMS.items()
    ]
