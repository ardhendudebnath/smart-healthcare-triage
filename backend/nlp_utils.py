"""Symptom extraction using spaCy lemmatization, fuzzy matching, and negation detection.

The vocabulary itself lives in symptoms.py. This module only decides which of
those symptoms a piece of free text mentions.
"""

from typing import List, Set

import spacy
from rapidfuzz import fuzz
from spacy.matcher import PhraseMatcher

from phrases_indic import extract_indic
from symptoms import SYMPTOM_PHRASES

nlp = spacy.load("en_core_web_sm")

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

# Longest phrase in the vocabulary, in words. Bounds how many n-gram sizes a
# request has to build. Derived rather than hardcoded so adding a longer phrase
# to symptoms.py cannot silently make it unmatchable.
MAX_PHRASE_WORDS = max(
    len(phrase.split()) for phrases in SYMPTOM_PHRASES.values() for phrase in phrases
)

# A token run spanning one of these joins two separate complaints, so comparing
# it against a phrase that has no conjunction of its own is meaningless — and
# occasionally harmful, because short function words hide inside longer ones.
# "my knee is swollen and painful" produced the run "swollen and", which scored
# 92 against the phrase "swollen gland" purely because "and" sits inside
# "gland", and reported swollen glands to someone with a swollen knee.
#
# Phrases that legitimately contain a conjunction ("pins and needles", "red and
# swollen skin") are still matched, by requiring the phrase to contain the same
# conjunction rather than dropping such runs outright.
CONJUNCTIONS = {"and", "or", "but", "nor", "plus"}


def _build_matcher() -> PhraseMatcher:
    matcher = PhraseMatcher(nlp.vocab, attr="LEMMA")
    for symptom, phrases in SYMPTOM_PHRASES.items():
        # Patterns must go through the full pipeline, not make_doc — the LEMMA
        # attribute is only populated by the lemmatizer component.
        matcher.add(symptom, list(nlp.pipe(phrases)))
    return matcher


matcher = _build_matcher()

# Phrases grouped by word count, per symptom, built once at import. The fuzzy
# pass compares each phrase only against token runs of the same length, so this
# is the shape it needs. Each phrase carries the set of conjunctions it contains
# so the run check does not have to re-split it on every request.
PHRASES_BY_WORD_COUNT = {}
for _symptom, _phrases in SYMPTOM_PHRASES.items():
    _grouped = {}
    for _phrase in _phrases:
        _words = _phrase.split()
        _grouped.setdefault(len(_words), []).append(
            (_phrase, CONJUNCTIONS.intersection(_words))
        )
    PHRASES_BY_WORD_COUNT[_symptom] = _grouped


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
    """Catch misspellings the exact matcher missed, e.g. 'chets pain', 'feverr'.

    Negated tokens are stripped before matching. Fuzzy matching runs on the
    whole sentence, so without this it would happily re-find a symptom the
    user just denied — the phrase matcher's negation handling can't protect a
    symptom it never matched in the first place.

    Each phrase is compared with `ratio` against runs of tokens the same length
    as the phrase, rather than with `partial_ratio` against the whole sentence.
    `partial_ratio` looks like the natural choice for finding a phrase inside a
    longer description, but it ignores word boundaries, and at 79 symptoms that
    breaks badly in two ways:

    - Short phrases become substring searches. "burn" scores 100 against
      "burning when I urinate", reporting a burn injury to someone with a urine
      infection.
    - Phrases sharing a prefix bleed into each other. "swollen legs" matched
      swollen gums, swollen lips, swollen glands and swollen joints all at once.

    Anchoring both ends against equal-length token runs fixes both, because the
    comparison has to account for the whole phrase: "burn" vs "burning" scores
    73 and is rejected, "swollen gum" vs "swollen leg" scores 73 and is
    rejected, while a typed "feverr" vs "fever" scores 91 and is accepted.

    The limit of this approach is transposition-heavy typos: "naseua" for
    "nausea" scores below the threshold and is missed. Lowering the threshold to
    catch it brings the prefix collisions straight back, so it stays missed —
    the exact matcher and the LLM path both cover ordinary phrasing anyway.
    """
    found = set()
    tokens = [
        token.lemma_.lower()
        for token in doc
        if not token.is_punct and token.i not in negated_indices
    ]
    if not tokens:
        return found

    # Token runs by length, built once per request and shared across all
    # symptoms — the inner loop would otherwise rebuild them ~450 times. Each
    # run is paired with the conjunctions it spans, so the check below is a set
    # comparison rather than a re-split.
    runs = {}
    for n in range(1, MAX_PHRASE_WORDS + 1):
        sized = []
        for i in range(len(tokens) - n + 1):
            window = tokens[i : i + n]
            sized.append((" ".join(window), CONJUNCTIONS.intersection(window)))
        runs[n] = sized

    for symptom, grouped in PHRASES_BY_WORD_COUNT.items():
        if symptom in already_found:
            continue
        for word_count, phrases in grouped.items():
            candidates = runs.get(word_count, ())
            if any(
                joined.issubset(phrase_conjunctions)
                and fuzz.ratio(phrase, run) >= FUZZY_THRESHOLD
                for phrase, phrase_conjunctions in phrases
                for run, joined in candidates
            ):
                found.add(symptom)
                break
    return found


def extract_symptoms(text: str) -> List[str]:
    """Extract symptom identifiers from free-text description.

    Handles word-form variation via lemmatization, typos via fuzzy matching,
    and drops symptoms the user explicitly denied ("no fever").

    Hindi and Bengali get a separate, much narrower pass — see phrases_indic.py
    for why offline coverage in those languages is red flags only.
    """
    if not text or not text.strip():
        return []

    found_indic = set(extract_indic(text))

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

    # Indic matches are unioned in rather than merged before the English passes:
    # they come from literal substring matching and must not be handed to the
    # English negation logic, which would be reasoning about tokens spaCy could
    # not parse in the first place.
    return sorted(found | found_indic)
