"""The symptom vocabulary: what the app can recognise, and how serious each one is.

This is the single source of truth. nlp_utils.py builds its matcher from it,
llm_extract.py builds its allowed-value list from it, knowledge_graph.py reads
the weights, specialties.py routes on the body system, and the frontend shows
the labels and descriptions. Adding a symptom here makes it work everywhere.

⚠️  NOT CLINICALLY REVIEWED  ⚠️
Phrasings and weights were assembled from commonly published patient-facing
warning signs (NHS "when to call 999" pages, stroke FAST signs, meningitis and
sepsis red flags). No clinician has reviewed them. Same caveat as
knowledge_graph.py and contacts.py: fine for a prototype, not for real triage.

Why each symptom carries a description
--------------------------------------
The UI used to print raw identifiers at people -- "one_sided_weakness" -- which
is meaningless to anyone who is frightened and looking for help. Every symptom
now has a plain-language label and one sentence a non-medical person can read
back and check against how they actually feel.

Why weights exist
-----------------
With 16 symptoms you can hand-list every combination that matters. With ~75 you
cannot: the pair count alone is in the thousands. So each symptom gets a weight,
and knowledge_graph.py falls back to summing weights for combinations nobody
curated. Curated rules still win -- the weight is the safety net, not the
primary mechanism.
"""

from dataclasses import dataclass, field
from typing import Dict, List

# --- Severity weights -------------------------------------------------------
# Deliberately coarse. A finer scale would imply precision this data does not
# have.
MINOR = 0        # Uncomfortable, not a reason to seek care on its own.
ORDINARY = 1     # Worth a doctor's opinion, not time-critical.
CONCERNING = 2   # Should be seen the same day if it stands alone.
RED_FLAG = 3     # Can indicate something life-threatening.

# --- Body systems -----------------------------------------------------------
# The key is also what specialties.py routes on, so these names are load-bearing.
SYSTEMS: Dict[str, str] = {
    "cardiac": "Heart and circulation",
    "respiratory": "Breathing and lungs",
    "neurological": "Brain and nerves",
    "digestive": "Stomach and digestion",
    "urinary": "Kidneys and urination",
    "musculoskeletal": "Bones, joints and muscles",
    "ent": "Ear, nose and throat",
    "eye": "Eyes and vision",
    "dental": "Teeth and gums",
    "skin": "Skin, hair and nails",
    "general": "Whole-body and general",
    "mental_health": "Mental health",
    "womens_health": "Women's health and pregnancy",
    "child": "Babies and young children",
}


@dataclass(frozen=True)
class Symptom:
    """One recognisable symptom.

    `phrases` are matched on lemmas by nlp_utils.py, so only the base form needs
    listing: "cough" also catches "coughing" and "coughed". Contractions are the
    exception -- both "cannot" and "can not" are listed because spaCy splits
    "can't" into two tokens.
    """

    id: str
    label: str
    description: str
    system: str
    weight: int
    phrases: List[str] = field(default_factory=list)


# Ordered by body system for readability. Order has no effect on matching.
SYMPTOMS: List[Symptom] = [
    # ---------------------------------------------------------------- cardiac
    Symptom(
        id="chest_pain",
        label="Chest pain",
        description="Pain, tightness, heaviness or pressure anywhere in the chest.",
        system="cardiac",
        weight=RED_FLAG,
        phrases=[
            "chest pain",
            "chest hurt",
            "pain in my chest",
            "chest tightness",
            "tight chest",
            "chest is tight",
            "chest feels tight",
            "chest pressure",
            "pressure in my chest",
            "heaviness in my chest",
            "crushing feeling in my chest",
        ],
    ),
    Symptom(
        id="palpitations",
        label="Heart racing or fluttering",
        description="Your heartbeat feels too fast, too strong, or irregular.",
        system="cardiac",
        weight=CONCERNING,
        phrases=[
            "palpitation",
            "heart racing",
            "heart is racing",
            "heart pounding",
            "heart beating fast",
            "irregular heartbeat",
            "heart skipping beat",
            "fluttering in my chest",
        ],
    ),
    Symptom(
        id="leg_swelling",
        label="Swollen legs, ankles or feet",
        description="Puffiness in the lower legs, often leaving a dent when pressed.",
        system="cardiac",
        weight=CONCERNING,
        phrases=[
            "swollen ankle",
            "swollen leg",
            "swollen feet",
            "swollen foot",
            "swelling in my leg",
            "swelling in my ankle",
            "puffy leg",
            "puffy ankle",
        ],
    ),
    Symptom(
        id="fainting",
        label="Fainting or nearly fainting",
        description="You lost consciousness briefly, or felt you were about to.",
        system="cardiac",
        weight=CONCERNING,
        phrases=[
            "fainted",
            "i faint",
            "nearly fainted",
            "almost fainted",
            "about to faint",
            "keep fainting",
            "syncope",
        ],
    ),
    Symptom(
        id="bluish_lips",
        label="Blue lips or fingertips",
        description="Lips, face or fingertips look blue or grey — a sign of low oxygen.",
        system="cardiac",
        weight=RED_FLAG,
        phrases=[
            "blue lip",
            "lips are blue",
            "lips look blue",
            "turning blue",
            "bluish skin",
            "fingertips are blue",
            "going grey",
        ],
    ),
    # ------------------------------------------------------------ respiratory
    Symptom(
        id="difficulty_breathing",
        label="Difficulty breathing",
        description="Breathing feels hard, or you are short of breath at rest.",
        system="respiratory",
        weight=RED_FLAG,
        phrases=[
            "difficulty breathing",
            "trouble breathing",
            "hard to breathe",
            "can not breathe",
            "cannot breathe",
            "short of breath",
            "shortness of breath",
            "breathless",
            "gasping",
            "struggling to breathe",
            "out of breath at rest",
        ],
    ),
    Symptom(
        id="cough",
        label="Cough",
        description="A new or ongoing cough, dry or bringing something up.",
        system="respiratory",
        weight=ORDINARY,
        phrases=[
            "cough",
            "coughing fit",
            "dry cough",
            "wet cough",
            "persistent cough",
        ],
    ),
    Symptom(
        id="coughing_blood",
        label="Coughing up blood",
        description="Blood or rust-coloured streaks in what you cough up.",
        system="respiratory",
        weight=RED_FLAG,
        phrases=[
            "coughing blood",
            "coughing up blood",
            "blood in my cough",
            "blood when i cough",
            "blood in my phlegm",
            "blood in my sputum",
        ],
    ),
    Symptom(
        id="wheezing",
        label="Wheezing",
        description="A whistling or squeaky sound when you breathe out.",
        system="respiratory",
        weight=CONCERNING,
        phrases=[
            "wheeze",
            "wheezing",
            "whistling when i breathe",
            "whistling sound in my chest",
            "chest whistles",
        ],
    ),
    Symptom(
        id="sputum",
        label="Phlegm or chest congestion",
        description="Bringing up mucus, or a blocked, heavy feeling in the chest.",
        system="respiratory",
        weight=ORDINARY,
        phrases=[
            "phlegm",
            "mucus",
            "sputum",
            "chest congestion",
            "congested chest",
            "yellow phlegm",
            "green phlegm",
        ],
    ),
    # ----------------------------------------------------------- neurological
    Symptom(
        id="headache",
        label="Headache",
        description="Pain anywhere in the head, including migraine.",
        system="neurological",
        weight=ORDINARY,
        phrases=[
            "headache",
            "head ache",
            "head hurt",
            "head is killing me",
            "migraine",
            "pain in my head",
            "splitting head",
        ],
    ),
    Symptom(
        id="confusion",
        label="Confusion",
        description="Not thinking clearly, disoriented, or not making sense to others.",
        system="neurological",
        weight=RED_FLAG,
        phrases=[
            "confusion",
            "confused",
            "disoriented",
            "not making sense",
            "can not think straight",
            "cannot think straight",
            "delirious",
            "does not know where he is",
            "does not know where she is",
        ],
    ),
    Symptom(
        id="neck_stiffness",
        label="Stiff neck",
        description="The neck is stiff or painful to bend forward — a meningitis warning sign.",
        system="neurological",
        weight=RED_FLAG,
        phrases=[
            "stiff neck",
            "neck stiffness",
            "neck is stiff",
            "can not move my neck",
            "cannot move my neck",
            "neck hurts to bend",
            "can not bend my neck",
            "cannot bend my neck",
        ],
    ),
    Symptom(
        id="slurred_speech",
        label="Slurred speech",
        description="Speech has become unclear or words will not come out — a stroke sign.",
        system="neurological",
        weight=RED_FLAG,
        phrases=[
            "slurred speech",
            "slurring",
            "speech is slurred",
            "can not speak properly",
            "cannot speak properly",
            "trouble speaking",
            "words are not coming out",
        ],
    ),
    Symptom(
        id="one_sided_weakness",
        label="Weakness on one side",
        description="Face, arm or leg weak, numb or drooping on one side — a stroke sign.",
        system="neurological",
        weight=RED_FLAG,
        phrases=[
            "one side of my body",
            "left side is weak",
            "right side is weak",
            "face is drooping",
            "face drooping",
            "arm went numb",
            "numbness on one side",
            "can not move my arm",
            "cannot move my arm",
            "can not lift my arm",
            "cannot lift my arm",
        ],
    ),
    Symptom(
        id="seizure_symptom",
        label="Seizure or fit",
        description="Uncontrolled shaking or jerking, often with loss of awareness.",
        system="neurological",
        weight=RED_FLAG,
        phrases=[
            "seizure",
            "convulsion",
            "having a fit",
            "shaking uncontrollably",
            "jerking movement",
            "body went stiff and shook",
        ],
    ),
    Symptom(
        id="dizziness",
        label="Dizziness",
        description="Feeling lightheaded, unsteady, or that the room is spinning.",
        system="neurological",
        weight=ORDINARY,
        phrases=[
            "dizziness",
            "dizzy",
            "lightheaded",
            "light headed",
            "room is spinning",
            "feel faint",
            "vertigo",
        ],
    ),
    Symptom(
        id="numbness",
        label="Numbness or tingling",
        description="Loss of feeling, or a pins-and-needles sensation.",
        system="neurological",
        weight=CONCERNING,
        phrases=[
            "numbness",
            "numb",
            "tingling",
            "pins and needles",
            "lost feeling in my",
            "can not feel my",
            "cannot feel my",
        ],
    ),
    Symptom(
        id="memory_loss",
        label="Memory problems",
        description="Forgetting things much more than usual, or gaps in memory.",
        system="neurological",
        weight=CONCERNING,
        phrases=[
            "memory loss",
            "losing my memory",
            "forgetting thing",
            "can not remember",
            "cannot remember",
            "very forgetful",
        ],
    ),
    Symptom(
        id="tremor",
        label="Shaking or tremor",
        description="Hands or another body part shake when you are not trying to move.",
        system="neurological",
        weight=ORDINARY,
        phrases=[
            "tremor",
            "hands shake",
            "shaky hands",
            "hands are trembling",
            "trembling",
        ],
    ),
    Symptom(
        id="balance_problems",
        label="Loss of balance",
        description="Unsteady on your feet, veering to one side, or falling.",
        system="neurological",
        weight=CONCERNING,
        phrases=[
            "loss of balance",
            "lost my balance",
            "unsteady",
            "keep falling",
            "can not walk straight",
            "cannot walk straight",
            "stumbling",
        ],
    ),
    # -------------------------------------------------------------- digestive
    Symptom(
        id="abdominal_pain",
        label="Stomach or abdominal pain",
        description="Pain, cramping or aching anywhere in the belly.",
        system="digestive",
        weight=CONCERNING,
        phrases=[
            "stomach pain",
            "stomach ache",
            "stomach hurt",
            "tummy pain",
            "tummy ache",
            "abdominal pain",
            "belly pain",
            "stomach cramp",
            "pain in my stomach",
        ],
    ),
    Symptom(
        id="nausea",
        label="Feeling sick (nausea)",
        description="Feeling like you might vomit, without necessarily doing so.",
        system="digestive",
        weight=ORDINARY,
        phrases=[
            "nausea",
            "nauseous",
            "feel sick",
            "feeling sick",
            "sick to my stomach",
            "queasy",
        ],
    ),
    Symptom(
        id="vomiting",
        label="Vomiting",
        description="Actually being sick, or unable to keep food and drink down.",
        system="digestive",
        weight=CONCERNING,
        phrases=[
            "vomit",
            "vomiting",
            "throwing up",
            "throw up",
            "been sick",
            "can not keep anything down",
            "cannot keep anything down",
        ],
    ),
    Symptom(
        id="vomiting_blood",
        label="Vomiting blood",
        description="Blood in your vomit, or vomit that looks like coffee grounds.",
        system="digestive",
        weight=RED_FLAG,
        phrases=[
            "vomiting blood",
            "throwing up blood",
            "blood in my vomit",
            "coffee ground vomit",
        ],
    ),
    Symptom(
        id="diarrhea",
        label="Diarrhoea",
        description="Loose or watery stools, more often than normal.",
        system="digestive",
        weight=ORDINARY,
        phrases=[
            "diarrhea",
            "diarrhoea",
            "loose motion",
            "loose stool",
            "watery stool",
            "upset stomach",
        ],
    ),
    Symptom(
        id="constipation",
        label="Constipation",
        description="Not passing stool, or straining and passing hard stool.",
        system="digestive",
        weight=ORDINARY,
        phrases=[
            "constipation",
            "constipated",
            "can not pass stool",
            "cannot pass stool",
            "hard stool",
            "not been to the toilet",
        ],
    ),
    Symptom(
        id="blood_in_stool",
        label="Blood in stool",
        description="Red blood when you pass stool, or stool that is black and tarry.",
        system="digestive",
        weight=RED_FLAG,
        phrases=[
            "blood in my stool",
            "blood in my poo",
            "black stool",
            "tarry stool",
            "rectal bleeding",
            "bleeding from my bottom",
            "blood when i pass stool",
        ],
    ),
    Symptom(
        id="heartburn",
        label="Heartburn or acidity",
        description="Burning behind the breastbone, often after eating or lying down.",
        system="digestive",
        weight=ORDINARY,
        phrases=[
            "heartburn",
            "acid reflux",
            "acidity",
            "burning after eating",
            "acid coming up",
        ],
    ),
    Symptom(
        id="jaundice",
        label="Yellow skin or eyes (jaundice)",
        description="Skin or the whites of the eyes have turned yellow.",
        system="digestive",
        weight=RED_FLAG,
        phrases=[
            "jaundice",
            "yellow eye",
            "eyes look yellow",
            "yellow skin",
            "skin turning yellow",
        ],
    ),
    Symptom(
        id="loss_of_appetite",
        label="Loss of appetite",
        description="Not wanting to eat, or eating much less than usual.",
        system="digestive",
        weight=ORDINARY,
        phrases=[
            "loss of appetite",
            "no appetite",
            "not eating",
            "do not feel like eating",
            "can not eat",
            "cannot eat",
        ],
    ),
    Symptom(
        id="difficulty_swallowing",
        label="Difficulty swallowing",
        description="Food or liquid sticks, or swallowing takes effort.",
        system="digestive",
        weight=CONCERNING,
        phrases=[
            "difficulty swallowing",
            "trouble swallowing",
            "food gets stuck",
            "can not swallow",
            "cannot swallow",
        ],
    ),
    Symptom(
        id="bloating",
        label="Bloating",
        description="The belly feels full, tight or swollen with gas.",
        system="digestive",
        weight=MINOR,
        phrases=[
            "bloated",
            "bloating",
            "stomach feels full",
            "swollen stomach",
            "gassy",
        ],
    ),
    # ---------------------------------------------------------------- urinary
    Symptom(
        id="painful_urination",
        label="Pain or burning when urinating",
        description="Stinging or burning as you pass urine.",
        system="urinary",
        weight=CONCERNING,
        phrases=[
            "painful urination",
            "burning when i urinate",
            "burning when i pee",
            "hurts to pee",
            "hurts to urinate",
            "stinging when i pee",
        ],
    ),
    Symptom(
        id="blood_in_urine",
        label="Blood in urine",
        description="Urine looks red, pink or brown.",
        system="urinary",
        weight=RED_FLAG,
        phrases=[
            "blood in my urine",
            "blood when i pee",
            "red urine",
            "pink urine",
            "brown urine",
        ],
    ),
    Symptom(
        id="frequent_urination",
        label="Urinating very often",
        description="Needing to pass urine far more often than usual.",
        system="urinary",
        weight=ORDINARY,
        phrases=[
            "frequent urination",
            "urinating often",
            "peeing a lot",
            "peeing all the time",
            "keep needing the toilet",
        ],
    ),
    Symptom(
        id="unable_to_urinate",
        label="Unable to pass urine",
        description="You need to urinate but cannot, or have not passed urine all day.",
        system="urinary",
        weight=RED_FLAG,
        phrases=[
            "can not urinate",
            "cannot urinate",
            "can not pass urine",
            "cannot pass urine",
            "can not pee",
            "cannot pee",
            "not passed urine",
        ],
    ),
    Symptom(
        id="flank_pain",
        label="Pain in the side or lower back",
        description="Pain in the side between the ribs and hip, often coming in waves.",
        system="urinary",
        weight=CONCERNING,
        phrases=[
            "flank pain",
            "pain in my side",
            "pain in my kidney",
            "kidney pain",
            "loin pain",
        ],
    ),
    # -------------------------------------------------------- musculoskeletal
    Symptom(
        id="joint_pain",
        label="Joint pain",
        description="Pain in a knee, shoulder, hip, elbow, wrist or other joint.",
        system="musculoskeletal",
        weight=ORDINARY,
        phrases=[
            "joint pain",
            "knee pain",
            "shoulder pain",
            "elbow pain",
            "hip pain",
            "wrist pain",
            "aching joint",
            "my knee hurts",
        ],
    ),
    Symptom(
        id="joint_swelling",
        label="Swollen joint",
        description="A joint is visibly swollen, hot or red.",
        system="musculoskeletal",
        weight=CONCERNING,
        phrases=[
            "swollen joint",
            "swollen knee",
            "swollen elbow",
            "swollen wrist",
            "joint is swollen",
            "knee is swollen",
            "hot swollen joint",
        ],
    ),
    Symptom(
        id="back_pain",
        label="Back pain",
        description="Pain anywhere in the back, upper or lower.",
        system="musculoskeletal",
        weight=ORDINARY,
        phrases=[
            "back pain",
            "backache",
            "lower back pain",
            "my back hurt",
            "pain in my back",
        ],
    ),
    Symptom(
        id="muscle_pain",
        label="Muscle or body ache",
        description="Aching muscles, or aching all over.",
        system="musculoskeletal",
        weight=ORDINARY,
        phrases=[
            "muscle pain",
            "muscle ache",
            "body ache",
            "body pain",
            "aching all over",
            "sore muscle",
        ],
    ),
    Symptom(
        id="injury_fracture",
        label="Injury or possible broken bone",
        description="A fall or blow, with a limb that looks wrong or cannot take weight.",
        system="musculoskeletal",
        weight=RED_FLAG,
        phrases=[
            "broken bone",
            "broke my arm",
            "broke my leg",
            "broke my wrist",
            "fracture",
            "bone is sticking out",
            "can not put weight on",
            "cannot put weight on",
            "limb looks bent",
        ],
    ),
    Symptom(
        id="limited_movement",
        label="Cannot move a joint normally",
        description="A joint is stuck, locked, or will not bend as it should.",
        system="musculoskeletal",
        weight=CONCERNING,
        phrases=[
            "can not move my leg",
            "cannot move my leg",
            "can not bend my knee",
            "cannot bend my knee",
            "joint is locked",
            "stiff joint",
        ],
    ),
    Symptom(
        id="neck_pain",
        label="Neck pain",
        description="Aching or sore neck that still moves normally.",
        system="musculoskeletal",
        weight=ORDINARY,
        phrases=[
            "neck pain",
            "neck is sore",
            "sore neck",
            "aching neck",
        ],
    ),
    # -------------------------------------------------------------------- ENT
    Symptom(
        id="sore_throat",
        label="Sore throat",
        description="Throat pain, especially when swallowing.",
        system="ent",
        weight=ORDINARY,
        phrases=[
            "sore throat",
            "throat pain",
            "throat hurt",
            "painful swallowing",
            "hurts to swallow",
            "scratchy throat",
        ],
    ),
    Symptom(
        id="ear_pain",
        label="Earache",
        description="Pain inside or around the ear.",
        system="ent",
        weight=ORDINARY,
        phrases=[
            "ear pain",
            "earache",
            "ear hurt",
            "pain in my ear",
            "ear is blocked",
        ],
    ),
    Symptom(
        id="hearing_loss",
        label="Hearing loss or ringing",
        description="Reduced hearing, or a persistent ringing sound.",
        system="ent",
        weight=CONCERNING,
        phrases=[
            "hearing loss",
            "can not hear",
            "cannot hear",
            "hard of hearing",
            "ringing in my ear",
            "tinnitus",
        ],
    ),
    Symptom(
        id="blocked_nose",
        label="Blocked or runny nose",
        description="Congestion, sneezing, or a nose that keeps running.",
        system="ent",
        weight=MINOR,
        phrases=[
            "blocked nose",
            "stuffy nose",
            "runny nose",
            "sneezing",
            "nasal congestion",
        ],
    ),
    Symptom(
        id="nosebleed",
        label="Nosebleed",
        description="Bleeding from the nose.",
        system="ent",
        weight=CONCERNING,
        phrases=[
            "nosebleed",
            "nose bleed",
            "bleeding from my nose",
            "blood from my nose",
        ],
    ),
    Symptom(
        id="hoarseness",
        label="Hoarse voice",
        description="Voice has gone croaky, weak, or disappeared.",
        system="ent",
        weight=ORDINARY,
        phrases=[
            "hoarse",
            "hoarseness",
            "lost my voice",
            "voice is croaky",
            "voice has changed",
        ],
    ),
    # -------------------------------------------------------------------- eye
    # Sudden vision loss and double vision are as much neurological signs as eye
    # ones, but both are red-flagged, so the routing hardly matters -- these go
    # to an eye specialist because that is who a patient can actually reach.
    Symptom(
        id="vision_loss",
        label="Sudden loss of vision",
        description="Vision has gone dark or disappeared, in one eye or both.",
        system="eye",
        weight=RED_FLAG,
        phrases=[
            "lost my vision",
            "lost my sight",
            "can not see",
            "cannot see",
            "sudden blindness",
            "vision went dark",
            "curtain over my eye",
            "went blind",
        ],
    ),
    Symptom(
        id="double_vision",
        label="Double or blurred vision",
        description="Seeing two of everything, or vision has become blurry.",
        system="eye",
        weight=CONCERNING,
        phrases=[
            "double vision",
            "seeing double",
            "blurred vision",
            "blurry vision",
            "vision is blurry",
        ],
    ),
    Symptom(
        id="eye_pain",
        label="Eye pain",
        description="Pain in or around the eye, sometimes with light sensitivity.",
        system="eye",
        weight=CONCERNING,
        phrases=[
            "eye pain",
            "eye hurt",
            "painful eye",
            "pain in my eye",
            "light hurts my eye",
        ],
    ),
    Symptom(
        id="red_eye",
        label="Red or itchy eye",
        description="The eye looks red or bloodshot, or itches and waters.",
        system="eye",
        weight=ORDINARY,
        phrases=[
            "red eye",
            "bloodshot eye",
            "pink eye",
            "itchy eye",
            "watery eye",
        ],
    ),
    # ----------------------------------------------------------------- dental
    Symptom(
        id="toothache",
        label="Toothache or gum pain",
        description="Pain in a tooth or the gums, sometimes with swelling.",
        system="dental",
        weight=ORDINARY,
        phrases=[
            "toothache",
            "tooth pain",
            "tooth hurt",
            "gum pain",
            "swollen gum",
            "my tooth is killing me",
        ],
    ),
    # ------------------------------------------------------------------- skin
    Symptom(
        id="rash",
        label="Rash",
        description="A new area of spots, redness or raised bumps on the skin.",
        system="skin",
        weight=ORDINARY,
        phrases=[
            "rash",
            "skin rash",
            "red spot",
            "hives",
            "breaking out",
        ],
    ),
    Symptom(
        id="itching",
        label="Itchy skin",
        description="Persistent itching, with or without a visible rash.",
        system="skin",
        weight=MINOR,
        phrases=[
            "itching",
            "itchy skin",
            "very itchy",
            "keep scratching",
        ],
    ),
    Symptom(
        id="skin_infection",
        label="Skin infection",
        description="Skin that is hot, red, spreading, or leaking pus.",
        system="skin",
        weight=CONCERNING,
        phrases=[
            "skin infection",
            "abscess",
            "boil on my",
            "pus coming out",
            "infected wound",
            "red and swollen skin",
            "cellulitis",
        ],
    ),
    Symptom(
        id="wound",
        label="Cut or wound",
        description="A break in the skin from an injury.",
        system="skin",
        weight=CONCERNING,
        phrases=[
            "deep cut",
            "bad cut",
            "open wound",
            "laceration",
            "gash",
            "cut myself",
        ],
    ),
    Symptom(
        id="burn",
        label="Burn or scald",
        description="Skin damaged by heat, hot liquid, chemicals or electricity.",
        system="skin",
        weight=CONCERNING,
        phrases=[
            "burnt my",
            "burned my",
            "burn injury",
            "scalded",
            "boiling water on my",
            "hot oil on my",
        ],
    ),
    # ---------------------------------------------------------------- general
    Symptom(
        id="fever",
        label="Fever",
        description="Raised temperature, feeling hot, or shivering with chills.",
        system="general",
        # ORDINARY rather than CONCERNING on purpose. Fever is the most common
        # thing anyone reports, and grading every fever as same-day care would
        # make the app cry wolf. What matters is fever *plus* something else, and
        # knowledge_graph.py curates those pairs explicitly.
        weight=ORDINARY,
        phrases=[
            "fever",
            "feverish",
            "high temperature",
            "running a temperature",
            "burning up",
            "chills",
            "shivering",
        ],
    ),
    Symptom(
        id="fatigue",
        label="Tiredness or weakness",
        description="Unusually tired or weak, not explained by activity or sleep.",
        system="general",
        weight=ORDINARY,
        phrases=[
            "fatigue",
            "very tired",
            "exhausted",
            "no energy",
            "weakness",
            "worn out",
            "run down",
        ],
    ),
    Symptom(
        id="weight_loss",
        label="Unexplained weight loss",
        description="Losing weight without trying to.",
        system="general",
        weight=CONCERNING,
        phrases=[
            "losing weight",
            "weight loss",
            "lost weight without trying",
            "clothes are loose",
        ],
    ),
    Symptom(
        id="night_sweats",
        label="Night sweats",
        description="Sweating heavily at night, enough to soak clothes or bedding.",
        system="general",
        weight=CONCERNING,
        phrases=[
            "night sweat",
            "sweating at night",
            "drenched at night",
            "wake up soaked",
        ],
    ),
    Symptom(
        id="swollen_glands",
        label="Swollen glands or lumps in the neck",
        description="Tender swellings in the neck, armpit or groin.",
        system="general",
        weight=ORDINARY,
        phrases=[
            "swollen gland",
            "swollen lymph node",
            "lump in my neck",
            "lump in my armpit",
        ],
    ),
    Symptom(
        id="dehydration",
        label="Signs of dehydration",
        description="Very thirsty, dry mouth, passing little urine, or sunken eyes.",
        system="general",
        weight=CONCERNING,
        phrases=[
            "dehydrated",
            "dehydration",
            "very thirsty",
            "dry mouth",
            "not passing much urine",
            "sunken eye",
        ],
    ),
    Symptom(
        id="allergic_reaction",
        label="Allergic reaction",
        description="Swelling of the face, lips, tongue or throat after a trigger.",
        system="general",
        weight=RED_FLAG,
        phrases=[
            "allergic reaction",
            "anaphylaxis",
            "swollen face",
            "swollen lip",
            "swollen tongue",
            "throat closing",
            "throat is closing up",
        ],
    ),
    Symptom(
        id="lump",
        label="New lump or growth",
        description="A lump anywhere on the body that is new or getting bigger.",
        system="general",
        weight=CONCERNING,
        phrases=[
            "lump",
            "new lump",
            "hard lump",
            "found a lump",
            "growth on my",
            "swelling that will not go",
            "swelling that wont go",
        ],
    ),
    # ---------------------------------------------------------- mental health
    Symptom(
        id="low_mood",
        label="Low mood",
        description="Persistently sad, hopeless, or unable to enjoy anything.",
        system="mental_health",
        weight=ORDINARY,
        phrases=[
            "depressed",
            "depression",
            "very low",
            "feeling hopeless",
            "no interest in anything",
            "can not enjoy anything",
            "cannot enjoy anything",
        ],
    ),
    Symptom(
        id="anxiety",
        label="Anxiety or panic",
        description="Constant worry, or sudden episodes of fear with physical symptoms.",
        system="mental_health",
        weight=ORDINARY,
        phrases=[
            "anxious",
            "anxiety",
            "panic attack",
            "constant worry",
            "can not stop worrying",
            "cannot stop worrying",
            "on edge all the time",
        ],
    ),
    Symptom(
        id="insomnia",
        label="Trouble sleeping",
        description="Cannot fall asleep or stay asleep, night after night.",
        system="mental_health",
        weight=ORDINARY,
        phrases=[
            "insomnia",
            "can not sleep",
            "cannot sleep",
            "not sleeping",
            "awake all night",
            "trouble sleeping",
            # Insomnia is one of the few symptoms defined *by* a negation, which
            # puts it at odds with the negation detector: "I have not been able
            # to sleep" reads as a denial unless the negation falls inside the
            # matched phrase itself. Spelling these out keeps it inside.
            "not been able to sleep",
            "unable to sleep",
            "have not slept",
        ],
    ),
    # ----------------------------------------------------- women's health
    Symptom(
        id="heavy_periods",
        label="Heavy periods",
        description="Menstrual bleeding much heavier or longer than usual.",
        system="womens_health",
        weight=CONCERNING,
        phrases=[
            "heavy period",
            "heavy menstrual bleeding",
            "bleeding through pad",
            "period is very heavy",
        ],
    ),
    Symptom(
        id="missed_period",
        label="Missed or late period",
        description="A period has not arrived when expected.",
        system="womens_health",
        weight=ORDINARY,
        phrases=[
            "missed period",
            "period is late",
            "no period this month",
            "have not had my period",
        ],
    ),
    Symptom(
        id="pelvic_pain",
        label="Pelvic pain",
        description="Pain low in the abdomen or pelvis.",
        system="womens_health",
        weight=CONCERNING,
        phrases=[
            "pelvic pain",
            "pain in my pelvis",
            "pain low down in my belly",
        ],
    ),
    Symptom(
        id="pregnancy_bleeding",
        label="Bleeding during pregnancy",
        description="Any vaginal bleeding while pregnant.",
        system="womens_health",
        weight=RED_FLAG,
        phrases=[
            "bleeding while pregnant",
            "bleeding during pregnancy",
            "spotting while pregnant",
            "pregnant and bleeding",
        ],
    ),
    Symptom(
        id="pregnancy_pain",
        label="Pain during pregnancy",
        description="Abdominal pain or cramping while pregnant.",
        system="womens_health",
        weight=RED_FLAG,
        phrases=[
            "pregnant and in pain",
            "cramping while pregnant",
            "pregnant with stomach pain",
            "contraction",
        ],
    ),
    # -------------------------------------------------------------- children
    Symptom(
        id="child_not_feeding",
        label="Baby not feeding",
        description="A baby or young child is refusing feeds or not drinking.",
        system="child",
        weight=RED_FLAG,
        phrases=[
            "baby not feeding",
            "baby is not drinking",
            "refusing feed",
            "will not feed",
            "wont feed",
            "child is not drinking",
        ],
    ),
    Symptom(
        id="child_lethargy",
        label="Baby unusually drowsy or floppy",
        description="A baby or child is limp, listless, or hard to wake.",
        system="child",
        weight=RED_FLAG,
        phrases=[
            "baby is floppy",
            "baby is limp",
            "very sleepy baby",
            "listless child",
            "child will not wake",
            "hard to wake the baby",
        ],
    ),
]

# --- Derived lookups --------------------------------------------------------
# Built once at import. Everything downstream reads these rather than scanning
# the list.

BY_ID: Dict[str, Symptom] = {s.id: s for s in SYMPTOMS}

SYMPTOM_PHRASES: Dict[str, List[str]] = {s.id: s.phrases for s in SYMPTOMS}

WEIGHTS: Dict[str, int] = {s.id: s.weight for s in SYMPTOMS}

ALL_IDS: List[str] = sorted(BY_ID)


def weight_of(symptom_id: str) -> int:
    """Severity weight for a symptom, 0 for anything unrecognised.

    Unknown ids score 0 rather than raising: an LLM response that slips an
    invented name past validation should not take the endpoint down, and
    scoring it as harmless is safe because curated rules run first.
    """
    return WEIGHTS.get(symptom_id, 0)


def label_of(symptom_id: str) -> str:
    """Human-readable label, falling back to a tidied id."""
    symptom = BY_ID.get(symptom_id)
    if symptom:
        return symptom.label
    return symptom_id.replace("_", " ").capitalize()


def describe(symptom_ids: List[str]) -> List[Dict[str, str]]:
    """Expand ids into the label/description/system detail the frontend shows."""
    details = []
    for symptom_id in symptom_ids:
        symptom = BY_ID.get(symptom_id)
        if symptom is None:
            # Keep unrecognised ids visible rather than silently dropping them.
            details.append(
                {
                    "id": symptom_id,
                    "label": label_of(symptom_id),
                    "description": "",
                    "system": "general",
                }
            )
            continue
        details.append(
            {
                "id": symptom.id,
                "label": symptom.label,
                "description": symptom.description,
                "system": symptom.system,
            }
        )
    return details


def grouped_by_system() -> List[Dict[str, object]]:
    """The full vocabulary grouped for the frontend's symptom reference."""
    groups = []
    for system_id, system_label in SYSTEMS.items():
        members = [s for s in SYMPTOMS if s.system == system_id]
        if not members:
            continue
        groups.append(
            {
                "id": system_id,
                "label": system_label,
                "symptoms": [
                    {
                        "id": s.id,
                        "label": s.label,
                        "description": s.description,
                        "weight": s.weight,
                    }
                    for s in sorted(members, key=lambda s: s.label)
                ],
            }
        )
    return groups
