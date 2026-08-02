"""Patient context: how age and duration change the urgency of the same symptoms.

Symptom lists alone lose most of what a real triage nurse acts on. "Fever" in a
four-month-old and "fever" in a healthy thirty-year-old are the same word and
completely different situations, and until now this app answered both
identically. Duration matters just as much in the other direction: a cough for
two days is a cold, and a cough for four weeks is a TB screening referral.

These rules only ever escalate. Age and duration can raise a result but never
lower one, so a wrong or missing answer can make the app more cautious and never
less. Both fields are optional for the same reason -- someone frightened enough
to be typing symptoms should not be blocked by a form.

⚠️  NOT CLINICALLY REVIEWED  ⚠️
Same caveat as knowledge_graph.py. The age thresholds and duration cut-offs below
come from commonly published patient guidance, not from a clinician.
"""

from typing import Dict, List, Optional, Tuple

from safety import escalate

# --- Age bands --------------------------------------------------------------
# Ages are taken in whole years, so "0" means under one year old. That is coarser
# than the guidance it encodes -- fever in an under-three-month-old is the real
# red flag -- but asking for an infant's age in months is a form field almost
# nobody fills in correctly, and treating the whole first year as high risk errs
# in the safe direction.
INFANT_MAX = 0
YOUNG_CHILD_MAX = 5
OLDER_ADULT_MIN = 65

# Sanity bound. Anything outside this is a typo, and a typo must not silently
# drive a triage decision.
MAX_PLAUSIBLE_AGE = 120

# Symptoms that are materially more dangerous in a baby, who cannot report pain,
# dehydrates in hours rather than days, and shows fewer outward signs.
INFANT_EMERGENCY = {"fever", "vomiting", "diarrhea", "rash", "difficulty_breathing"}

# In under-fives, fluid loss is the main killer.
YOUNG_CHILD_ESCALATE = {"fever", "vomiting", "diarrhea", "dehydration", "cough"}

# In older adults, infection and falls both present atypically and deteriorate
# faster. Confusion especially: in an older adult it is often the first sign of
# an infection rather than a neurological problem.
OLDER_ADULT_ESCALATE = {
    "fever",
    "confusion",
    "fainting",
    "dehydration",
    "injury_fracture",
    "vomiting",
    "diarrhea",
    "chest_pain",
}

# --- Duration ---------------------------------------------------------------
# Ordered shortest to longest so comparisons are index arithmetic.
DURATIONS: List[str] = [
    "today",
    "days_1_3",
    "days_4_7",
    "weeks_1_3",
    "weeks_over_3",
]

DURATION_LABELS: Dict[str, str] = {
    "today": "Since today",
    "days_1_3": "1–3 days",
    "days_4_7": "4–7 days",
    "weeks_1_3": "1–3 weeks",
    "weeks_over_3": "More than 3 weeks",
}

# (symptom, minimum duration, key, explanation). A symptom that has outstayed
# its normal course is a different problem from the same symptom on day one.
#
# The key exists so i18n.py can translate the explanation. Same reasoning as
# knowledge_graph.py: rewording the English must not orphan the Hindi and
# Bengali versions.
DURATION_RULES: List[Tuple[str, str, str, str]] = [
    (
        # India screens for TB at three weeks of cough. This is the single most
        # useful duration rule in an Indian context and the reason duration was
        # worth collecting at all.
        "cough",
        "weeks_over_3",
        "dur_cough_tb",
        "A cough lasting more than three weeks should be checked for TB.",
    ),
    (
        "fever",
        "days_4_7",
        "dur_fever",
        "A fever lasting more than a few days should be assessed.",
    ),
    (
        "headache",
        "weeks_over_3",
        "dur_headache",
        "A headache going on for weeks should be looked at properly.",
    ),
    (
        "weight_loss",
        "weeks_1_3",
        "dur_weight_loss",
        "Weight loss over several weeks needs investigating.",
    ),
    (
        "night_sweats",
        "weeks_1_3",
        "dur_night_sweats",
        "Night sweats over several weeks need investigating.",
    ),
    (
        "diarrhea",
        "weeks_1_3",
        "dur_diarrhea",
        "Diarrhoea lasting weeks risks dehydration and needs a cause found.",
    ),
    (
        "hoarseness",
        "weeks_over_3",
        "dur_hoarseness",
        "A voice change lasting more than three weeks should be examined.",
    ),
    (
        "difficulty_swallowing",
        "weeks_1_3",
        "dur_swallowing",
        "Trouble swallowing that persists needs investigating.",
    ),
    (
        "lump",
        "weeks_1_3",
        "dur_lump",
        "A lump that has not gone after weeks should be examined.",
    ),
]

# Age explanations, keyed the same way. {age} is filled in by the caller so a
# translation can place the number where its own grammar needs it.
AGE_NOTES = {
    "ctx_infant": (
        "These symptoms in a baby under one need to be seen straight away."
    ),
    "ctx_young_child": (
        "Young children ({age} years old) dehydrate and deteriorate faster "
        "than adults."
    ),
    "ctx_older_adult": (
        "At {age}, these symptoms can be more serious than they appear."
    ),
}


def parse_age(raw) -> Optional[int]:
    """Whole years, or None if the value is missing or not usable.

    Returns None rather than raising or guessing. An unparseable age means the
    age rules simply do not run, which leaves the symptom-based result intact.
    """
    if raw is None or raw == "":
        return None
    try:
        age = int(float(raw))
    except (TypeError, ValueError):
        return None
    if age < 0 or age > MAX_PLAUSIBLE_AGE:
        return None
    return age


def normalise_duration(raw) -> Optional[str]:
    """A known duration key, or None."""
    if raw in DURATIONS:
        return raw
    return None


def _at_least(duration: str, threshold: str) -> bool:
    return DURATIONS.index(duration) >= DURATIONS.index(threshold)


def _note(key: str, english: str, raised: str = "", **params) -> Dict:
    """One explanation, in a shape i18n.py can translate.

    `raised` is "" (nothing changed), "one_level" or "emergency", so the caller
    can prefix the sentence in its own language rather than having English
    grammar baked into the note.
    """
    return {
        "key": key,
        "text": english.format(**params) if params else english,
        "params": params,
        "raised": raised,
    }


def apply(
    level: str,
    symptoms: List[str],
    age: Optional[int],
    duration: Optional[str],
) -> Tuple[str, List[Dict]]:
    """Escalate `level` for age and duration. Returns (level, explanations).

    Each rule contributes at most one step, and the whole function can only move
    the result up the scale. Explanations are returned rather than applied to the
    message so the frontend can show the user exactly which extra fact changed
    the answer -- an escalation nobody can account for reads as a malfunction.
    """
    notes: List[Dict] = []
    symptom_set = set(symptoms)

    if not symptom_set:
        # Nothing recognised. Escalating "unknown" on age alone would tell a
        # 70-year-old who typed nonsense to seek urgent care.
        return level, notes

    # Age and duration are both modifiers of the same underlying uncertainty, so
    # they escalate at most one level *between* them rather than one each.
    # Stacking sends a four-year-old with a five-day fever from "see your GP" to
    # "go to the emergency room", which is over-triage past the point of being
    # useful -- an app that shouts at everyone gets ignored by everyone. The
    # infant rule below is the deliberate exception.
    escalated_already = False

    if age is not None:
        if age <= INFANT_MAX and symptom_set & INFANT_EMERGENCY:
            if level != "emergency":
                level = "emergency"
                escalated_already = True
                notes.append(
                    _note("ctx_infant", AGE_NOTES["ctx_infant"], raised="emergency")
                )
        elif age <= YOUNG_CHILD_MAX and symptom_set & YOUNG_CHILD_ESCALATE:
            escalated = escalate(level)
            if escalated != level:
                level = escalated
                escalated_already = True
                notes.append(
                    _note(
                        "ctx_young_child",
                        AGE_NOTES["ctx_young_child"],
                        raised="one_level",
                        age=age,
                    )
                )
        elif age >= OLDER_ADULT_MIN and symptom_set & OLDER_ADULT_ESCALATE:
            escalated = escalate(level)
            if escalated != level:
                level = escalated
                escalated_already = True
                notes.append(
                    _note(
                        "ctx_older_adult",
                        AGE_NOTES["ctx_older_adult"],
                        raised="one_level",
                        age=age,
                    )
                )

    if duration is not None:
        for symptom, threshold, key, explanation in DURATION_RULES:
            if symptom not in symptom_set or not _at_least(duration, threshold):
                continue
            escalated = escalate(level)
            if escalated_already or escalated == level:
                # Either age already moved this result, or it is at the top
                # already. Either way the explanation still belongs on screen --
                # the duration is a real reason to be seen even when it did not
                # change the verdict.
                notes.append(_note(key, explanation))
            else:
                level = escalated
                notes.append(_note(key, explanation, raised="one_level"))
            break

    return level, notes


def options() -> List[Dict[str, str]]:
    """Duration choices for the frontend dropdown, shortest first."""
    return [{"id": key, "label": DURATION_LABELS[key]} for key in DURATIONS]
