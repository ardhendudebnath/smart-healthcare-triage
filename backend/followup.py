"""Follow-up questions: the two or three things a nurse would ask next.

Someone typing "I have a headache" has told the app almost nothing. A headache
that built over a day is ordinary; one that hit full force in seconds is a
possible bleed. Same four words, completely different answer. This module asks
the small number of questions that separate those cases.

IMPORTANT: like knowledge_graph.py, these questions are built from commonly
published warning signs and have NOT been reviewed by a clinician. They are a
prototype. Do not use for real triage without medical review.

Four rules hold this together
-----------------------------
1. Answers can only escalate, never de-escalate. This is the same principle
   context.py applies to age, and it is what makes the questions safe to answer
   carelessly. Chest pain is graded emergency on its own -- deliberate
   over-triage, because most chest pain is not cardiac and the cost of missing
   the cases that are is not comparable. Someone answering "no, it does not
   spread to my arm" must not undo that. A "no" here means "no new information",
   never "less urgent than we thought".

2. Nothing is asked once the result is already emergency. Someone with stroke
   signs needs to be told to call an ambulance, not handed a questionnaire. The
   grade cannot go higher, so every question would be a delay bought for
   nothing. Same for crisis: that person needs a counsellor's number in front of
   them immediately.

3. Answers are optional and the result stands without them. The first result is
   a real result, not a placeholder. Someone who closes the app after reading it
   has still been triaged.

4. Where an answer maps onto a symptom the vocabulary already knows, it adds
   that symptom and lets knowledge_graph.py re-grade, rather than hard-coding a
   new verdict here. Answering yes to "is your neck stiff?" adds neck_stiffness,
   and the existing headache+neck_stiffness meningitis rule fires on its own.
   That keeps one graded path through the app instead of two that can disagree,
   and every such answer is covered by the rule tests that already exist.

`escalates_to` is the exception, for red flags that are not symptoms in their
own right. Sudden onset is a property of a headache rather than a separate
complaint, so there is nothing sensible to add to the symptom list -- it goes
straight to a level instead.
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from knowledge_graph import assess_urgency

# Asking more than a few questions turns triage into a form, and someone worried
# about their chest will abandon it. Three is enough to catch the red flags that
# matter without becoming a questionnaire.
MAX_QUESTIONS = 3

# Every question takes the same three answers. A frightened person forced to
# choose between yes and no will guess, and a guess is worse than an admission
# of not knowing -- so "unsure" is always available, and it never escalates.
ANSWER_IDS = ("yes", "no", "unsure")


@dataclass(frozen=True)
class FollowUp:
    """One question, and what a "yes" to it means.

    `severity` orders the questions when more than MAX_QUESTIONS apply, so the
    three that get asked are the three that could change the answer most.
    """

    id: str
    triggers: FrozenSet[str]
    severity: int
    adds: Tuple[str, ...] = ()
    escalates_to: Optional[str] = None
    note_key: Optional[str] = None
    # Questions that only make sense below a certain grade. Asking someone
    # already told to attend today whether they can keep fluids down is still
    # useful; asking it of someone told to rest at home is where it changes most.
    max_level: Optional[str] = None


# Ordered by how much a "yes" changes the picture. Each one is a published
# warning sign, and each is phrased as something a person can actually answer
# about themselves without medical knowledge.
FOLLOW_UPS: List[FollowUp] = [
    # Thunderclap onset. The classic subarachnoid haemorrhage question, and the
    # single most valuable thing to ask anyone reporting a headache.
    FollowUp(
        id="headache_sudden",
        triggers=frozenset({"headache"}),
        severity=100,
        escalates_to="emergency",
        note_key="fu_note_headache_sudden",
    ),
    # The non-blanching rash of meningococcal sepsis. The glass test is standard
    # public health guidance precisely because a lay person can perform it.
    FollowUp(
        id="fever_rash",
        triggers=frozenset({"fever"}),
        severity=95,
        escalates_to="emergency",
        note_key="fu_note_fever_rash",
    ),
    # Adds the symptom and lets the existing meningitis combos fire.
    FollowUp(
        id="headache_neck",
        triggers=frozenset({"headache", "fever"}),
        severity=90,
        adds=("neck_stiffness",),
        note_key="fu_note_headache_neck",
    ),
    # Breathlessness at rest alongside a chest infection picture. Adds the
    # symptom, which is emergency on its own in knowledge_graph.py.
    FollowUp(
        id="breathless_at_rest",
        triggers=frozenset({"cough", "fever", "chest_pain"}),
        severity=85,
        adds=("difficulty_breathing",),
        note_key="fu_note_breathless",
    ),
    # Dehydration is what actually harms people with gastroenteritis, and it is
    # invisible in a symptom list that says only "vomiting".
    FollowUp(
        id="fluids_down",
        triggers=frozenset({"vomiting", "diarrhea", "fever"}),
        severity=70,
        escalates_to="urgent_care",
        note_key="fu_note_fluids",
    ),
    # Right iliac fossa pain: appendicitis until proven otherwise.
    FollowUp(
        id="abdominal_right_lower",
        triggers=frozenset({"abdominal_pain"}),
        severity=65,
        escalates_to="urgent_care",
        note_key="fu_note_abdominal",
    ),
]

BY_ID: Dict[str, FollowUp] = {question.id: question for question in FOLLOW_UPS}

# Grades at which no question is worth asking. See rule 2 in the module
# docstring: nothing can raise these, so every question is pure delay.
_TERMINAL_LEVELS = {"emergency", "crisis"}

_ORDER = ["unknown", "self_care", "urgent_care", "emergency"]


def _rank(level: str) -> int:
    return _ORDER.index(level) if level in _ORDER else 0


def questions_for(symptoms: List[str], level: str) -> List[Dict]:
    """Which questions to ask, most valuable first, capped at MAX_QUESTIONS.

    Returns keys rather than sentences, so i18n can translate them -- the same
    contract every other user-visible string in this app follows.
    """
    if level in _TERMINAL_LEVELS:
        return []

    # Nothing recognised means nothing to ask about. A question triggered by no
    # symptom would be a guess, and a guess dressed as a clinical question reads
    # far more authoritative than it deserves to.
    if not symptoms:
        return []

    present = set(symptoms)
    applicable = [
        question
        for question in FOLLOW_UPS
        if question.triggers & present
        and not (question.max_level and _rank(level) > _rank(question.max_level))
        # A question whose only effect is adding a symptom the patient has
        # already reported cannot change anything.
        and not (question.adds and set(question.adds) <= present)
    ]

    applicable.sort(key=lambda q: (-q.severity, q.id))
    return [
        {
            "id": question.id,
            "question_key": f"fu_q_{question.id}",
            "answers": [
                {"id": answer_id, "label_key": f"fu_a_{answer_id}"}
                for answer_id in ANSWER_IDS
            ],
        }
        for question in applicable[:MAX_QUESTIONS]
    ]


def apply(
    level: str, symptoms: List[str], answers: Dict[str, str]
) -> Tuple[str, List[str], List[str]]:
    """Re-grade with the answers folded in.

    Returns (level, symptoms, note_keys). Only "yes" does anything: "no" and
    "unsure" both mean "no new information", and neither can lower a grade.

    Unknown question ids and unknown answers are ignored rather than rejected. A
    stale client sending a question that no longer exists should still get a
    triage result -- refusing the whole request over one unrecognised key would
    turn a harmless mismatch into a failure to advise.
    """
    updated = list(symptoms)
    notes: List[str] = []
    forced_level = level

    for question_id, answer in answers.items():
        question = BY_ID.get(question_id)
        if question is None or answer != "yes":
            continue

        added = [s for s in question.adds if s not in updated]
        updated.extend(added)

        if question.escalates_to and _rank(question.escalates_to) > _rank(forced_level):
            forced_level = question.escalates_to

        if question.note_key and (added or question.escalates_to):
            notes.append(question.note_key)

    # Re-grade through the one existing engine, so an added symptom is graded by
    # the same curated rules as one the patient typed themselves.
    regraded = assess_urgency(updated)["level"] if updated != symptoms else level

    # The highest of the three wins, and the original level is included so this
    # can never come out below where it started.
    final = max([level, regraded, forced_level], key=_rank)
    return final, updated, notes
