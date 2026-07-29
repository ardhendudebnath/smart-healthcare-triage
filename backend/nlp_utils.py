"""Symptom extraction using spaCy lemmatization, fuzzy matching, and negation detection."""

from typing import List, Set

import spacy
from rapidfuzz import fuzz
from spacy.matcher import PhraseMatcher

nlp = spacy.load("en_core_web_sm")

# Each symptom maps to the phrases people actually use. Matching is done on
# lemmas, so "coughing" / "coughed" / "coughs" all reduce to "cough" and only
# the base form needs listing here.
SYMPTOM_PHRASES = {
    "chest_pain": [
        "chest pain",
        "chest hurt",
        "pain in my chest",
        "chest tightness",
        "tight chest",
        "chest is tight",
        "chest feels tight",
        "chest pressure",
        "pressure in my chest",
    ],
    "difficulty_breathing": [
        "difficulty breathing",
        "trouble breathing",
        "hard to breathe",
        "can not breathe",
        "cannot breathe",
        "short of breath",
        "shortness of breath",
        "breathless",
        "gasping",
        "wheeze",
    ],
    "fever": [
        "fever",
        "feverish",
        "high temperature",
        "running a temperature",
        "burning up",
        "chills",
    ],
    "cough": [
        "cough",
        "coughing fit",
        "dry cough",
        "wet cough",
    ],
    "nausea": [
        "nausea",
        "nauseous",
        "feel sick",
        "sick to my stomach",
        "vomit",
        "throwing up",
        "throw up",
        "queasy",
    ],
    "dizziness": [
        "dizziness",
        "dizzy",
        "lightheaded",
        "light headed",
        "spinning",
        "faint",
        "vertigo",
    ],
    "headache": [
        "headache",
        "head ache",
        "head hurt",
        "head is killing me",
        "migraine",
        "pain in my head",
        "splitting head",
    ],
    "abdominal_pain": [
        "stomach pain",
        "stomach ache",
        "stomach hurt",
        "tummy pain",
        "tummy ache",
        "abdominal pain",
        "belly pain",
        "cramps",
        "pain in my stomach",
    ],
    "sore_throat": [
        "sore throat",
        "throat pain",
        "throat hurt",
        "painful swallowing",
        "hurts to swallow",
        "scratchy throat",
    ],
    "diarrhea": [
        "diarrhea",
        "diarrhoea",
        "loose motion",
        "loose stool",
        "watery stool",
        "upset stomach",
    ],
    "fatigue": [
        "fatigue",
        "very tired",
        "exhausted",
        "no energy",
        "weakness",
        "worn out",
        "run down",
    ],
    "rash": [
        "rash",
        "skin rash",
        "red spots",
        "hives",
        "itchy skin",
        "breaking out",
    ],
    # --- Red-flag symptoms. These carry more weight in knowledge_graph.py ---
    "confusion": [
        "confusion",
        "confused",
        "disoriented",
        "not making sense",
        "can not think straight",
        "cannot think straight",
        "delirious",
    ],
    "neck_stiffness": [
        "stiff neck",
        "neck stiffness",
        "neck is stiff",
        "can not move my neck",
        "cannot move my neck",
        "neck hurts to bend",
    ],
    "slurred_speech": [
        "slurred speech",
        "slurring",
        "speech is slurred",
        "can not speak properly",
        "cannot speak properly",
        "trouble speaking",
        "words are not coming out",
    ],
    "one_sided_weakness": [
        "one side of my body",
        "left side is weak",
        "right side is weak",
        "face is drooping",
        "face drooping",
        "arm went numb",
        "numbness on one side",
        "can not move my arm",
        "cannot move my arm",
    ],
}

# Words that flip the meaning of a symptom mentioned after them.
NEGATION_TOKENS = {"no", "not", "never", "without", "deny", "denies", "n't"}

# Dependency labels that start a separate item from the negated one. In
# "cannot breathe and chest pain", `pain` is a conj of `breathe` — the user is
# reporting it, not denying it. Same for the appositive in
# "no trouble breathing, just a cough".
SCOPE_BREAK_DEPS = {"conj", "appos"}

# Minimum rapidfuzz score to accept a typo as a match. Below ~85 unrelated
# short words start colliding.
FUZZY_THRESHOLD = 86


def _build_matcher() -> PhraseMatcher:
    matcher = PhraseMatcher(nlp.vocab, attr="LEMMA")
    for symptom, phrases in SYMPTOM_PHRASES.items():
        # Patterns must go through the full pipeline, not make_doc — the LEMMA
        # attribute is only populated by the lemmatizer component.
        matcher.add(symptom, list(nlp.pipe(phrases)))
    return matcher


matcher = _build_matcher()


def _negation_scopes(doc) -> List[tuple]:
    """Find negations and the token span each one applies to.

    Returns (negation_index, negated_indices) pairs. The negation's own index
    is tracked so a phrase that *contains* the negation — "can't breathe",
    which spaCy tokenizes as ca/nt/breathe — isn't mistaken for a denial of
    itself. Getting this wrong would silently drop an emergency symptom.

    Scope comes from the dependency tree rather than a fixed token window: a
    window can't tell "no fever or chills" (both denied) from "cannot breathe
    and chest pain" (one denied, one reported).
    """
    scopes = []
    for token in doc:
        is_negation = token.lower_ in NEGATION_TOKENS or token.dep_ == "neg"
        if not is_negation:
            continue

        scope = set()
        for descendant in token.head.subtree:
            # Walk up from the descendant to the negated head; if we cross a
            # conj/appos edge, this token belongs to a sibling item and the
            # negation doesn't reach it.
            node, breaks_scope = descendant, False
            while node is not None and node != token.head:
                if node.dep_ in SCOPE_BREAK_DEPS:
                    breaks_scope = True
                    break
                node = node.head if node.head != node else None
            if not breaks_scope:
                scope.add(descendant.i)

        scopes.append((token.i, scope))
    return scopes


def _is_negated(start: int, end: int, scopes: List[tuple]) -> bool:
    """True if a match spanning [start, end) is denied by an outside negation."""
    span = range(start, end)
    for negation_idx, scope in scopes:
        # A negation inside the matched phrase is part of the symptom's own
        # wording, not a denial of it.
        if start <= negation_idx < end:
            continue
        if any(i in scope for i in span):
            return True
    return False


def _fuzzy_matches(doc, already_found: Set[str], negated_indices: Set[int]) -> Set[str]:
    """Catch misspellings the exact matcher missed, e.g. 'chets pain'.

    Negated tokens are stripped before matching. Fuzzy matching runs on the
    whole sentence, so without this it would happily re-find a symptom the
    user just denied — the phrase matcher's negation handling can't protect a
    symptom it never matched in the first place.
    """
    found = set()
    text = " ".join(
        token.lemma_.lower()
        for token in doc
        if not token.is_punct and token.i not in negated_indices
    )
    if not text.strip():
        return found

    for symptom, phrases in SYMPTOM_PHRASES.items():
        if symptom in already_found:
            continue
        for phrase in phrases:
            # partial_ratio finds the best-matching window, so a phrase can be
            # matched inside a longer sentence without splitting it manually.
            if fuzz.partial_ratio(phrase, text) >= FUZZY_THRESHOLD:
                found.add(symptom)
                break
    return found


def extract_symptoms(text: str) -> List[str]:
    """Extract symptom identifiers from free-text description.

    Handles word-form variation via lemmatization, typos via fuzzy matching,
    and drops symptoms the user explicitly denied ("no fever").
    """
    if not text or not text.strip():
        return []

    doc = nlp(text)
    scopes = _negation_scopes(doc)

    found = set()
    negated_symptoms = set()

    for match_id, start, end in matcher(doc):
        symptom = nlp.vocab.strings[match_id]
        if _is_negated(start, end, scopes):
            negated_symptoms.add(symptom)
        else:
            found.add(symptom)

    # Only fall back to fuzzy matching when the exact pass found nothing for a
    # symptom — it's looser and shouldn't override a clean negation.
    all_negated = set()
    for _, scope in scopes:
        all_negated |= scope
    for symptom in _fuzzy_matches(doc, found | negated_symptoms, all_negated):
        found.add(symptom)

    return sorted(found)
