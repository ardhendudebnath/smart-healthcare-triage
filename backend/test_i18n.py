"""Translation completeness tests. Run: python test_i18n.py

Missing translations fail quietly by design -- the string falls back to English
-- which is the right behaviour at runtime and the wrong behaviour in
development, because a half-translated app looks finished until someone who
does not read English uses it. These tests are what makes the gaps visible.
"""

import i18n
import translations_bn
import translations_hi
from context import AGE_NOTES, DURATION_RULES
from contacts import CONTACTS, CRISIS_CONTACTS
from knowledge_graph import (
    EMERGENCY_COMBOS,
    MESSAGES,
    REASON_TEMPLATES,
    URGENT_CARE_COMBOS,
)
from phrases_indic import RED_FLAG_PHRASES, extract_indic
from safety import check_crisis, check_emergency_override
from specialties import SPECIALTIES
from symptoms import ALL_IDS, SYSTEMS

TABLES = {"hi": translations_hi, "bn": translations_bn}


def _missing(table_dict, required):
    return sorted(k for k in required if not table_dict.get(k))


def test_every_symptom_is_translated():
    failures = []
    for lang, table in TABLES.items():
        missing = [s for s in ALL_IDS if s not in table.SYMPTOMS]
        if missing:
            failures.append(f"{lang}: {len(missing)} symptoms missing: {missing[:8]}")

        incomplete = [
            s
            for s in ALL_IDS
            if s in table.SYMPTOMS
            and not (table.SYMPTOMS[s].get("label") and table.SYMPTOMS[s].get("description"))
        ]
        if incomplete:
            failures.append(f"{lang}: incomplete entries: {incomplete[:8]}")
    assert not failures, "\n".join(failures)


def test_no_translations_for_symptoms_that_do_not_exist():
    """A stale entry is dead weight and hides a renamed symptom."""
    known = set(ALL_IDS)
    failures = []
    for lang, table in TABLES.items():
        stale = sorted(set(table.SYMPTOMS) - known)
        if stale:
            failures.append(f"{lang}: translations for unknown symptoms: {stale}")
    assert not failures, "\n".join(failures)


def test_ui_strings_are_complete():
    failures = []
    for lang, table in TABLES.items():
        missing = _missing(table.UI, i18n.UI_EN)
        if missing:
            failures.append(f"{lang}: missing UI strings: {missing}")
        stale = sorted(set(table.UI) - set(i18n.UI_EN))
        if stale:
            failures.append(f"{lang}: UI strings no longer used: {stale}")
    assert not failures, "\n".join(failures)


def test_every_rule_reason_is_translated():
    """Every keyed rule explanation must exist in both languages."""
    keys = set(REASON_TEMPLATES)
    for _, key, _ in EMERGENCY_COMBOS:
        keys.add(key)
    for _, key, _ in URGENT_CARE_COMBOS:
        keys.add(key)
    keys.add("several_symptoms")

    failures = []
    for lang, table in TABLES.items():
        missing = _missing(table.REASONS, keys)
        if missing:
            failures.append(f"{lang}: missing reasons: {missing}")
        stale = sorted(set(table.REASONS) - keys)
        if stale:
            failures.append(f"{lang}: reasons for rules that no longer exist: {stale}")
    assert not failures, "\n".join(failures)


def test_reason_templates_keep_their_placeholder():
    """A template that loses {names} would print a sentence with nothing in it."""
    failures = []
    for lang, table in TABLES.items():
        for key in REASON_TEMPLATES:
            translated = table.REASONS.get(key, "")
            if "{names}" not in translated:
                failures.append(f"{lang}: {key} is missing the {{names}} placeholder")
    assert not failures, "\n".join(failures)


def test_context_notes_are_translated():
    keys = set(AGE_NOTES) | {key for _, _, key, _ in DURATION_RULES}
    keys |= {"raised_one_level", "raised_emergency"}

    failures = []
    for lang, table in TABLES.items():
        missing = _missing(table.STRINGS, keys)
        if missing:
            failures.append(f"{lang}: missing context strings: {missing}")
    assert not failures, "\n".join(failures)


def test_age_notes_keep_their_placeholder():
    failures = []
    for lang, table in TABLES.items():
        for key, english in AGE_NOTES.items():
            if "{age}" not in english:
                continue
            translated = table.STRINGS.get(key, "")
            if "{age}" not in translated:
                failures.append(f"{lang}: {key} is missing the {{age}} placeholder")
    assert not failures, "\n".join(failures)


def test_safety_critical_strings_are_translated():
    """The disclaimer and the crisis message must never appear in English.

    These are the two strings someone most needs to understand: one says this is
    not a diagnosis, the other is what a person in crisis reads.
    """
    required = ["disclaimer", "crisis_message", "safety_escalated_severe",
                "safety_escalated_emergency"]
    failures = []
    for lang, table in TABLES.items():
        missing = _missing(table.STRINGS, required)
        if missing:
            failures.append(f"{lang}: missing: {missing}")
    assert not failures, "\n".join(failures)


def test_levels_specialties_systems_and_contacts_are_translated():
    numbers = {c["number"] for group in CONTACTS.values() for c in group}
    numbers |= {c["number"] for c in CRISIS_CONTACTS}

    failures = []
    for lang, table in TABLES.items():
        missing_levels = _missing(table.MESSAGES, MESSAGES)
        if missing_levels:
            failures.append(f"{lang}: missing urgency messages: {missing_levels}")

        missing_specialties = [s for s in SPECIALTIES if s not in table.SPECIALTIES]
        if missing_specialties:
            failures.append(f"{lang}: missing specialties: {missing_specialties}")

        missing_systems = [s for s in SYSTEMS if not table.SYSTEMS.get(s)]
        if missing_systems:
            failures.append(f"{lang}: missing body systems: {missing_systems}")

        missing_contacts = [n for n in numbers if n not in table.CONTACTS]
        if missing_contacts:
            failures.append(f"{lang}: missing helplines: {missing_contacts}")
    assert not failures, "\n".join(failures)


def test_unknown_language_falls_back_to_english():
    """A stale bookmark with ?lang=fr shows English, not an error."""
    assert i18n.normalise("fr") == "en"
    assert i18n.normalise(None) == "en"
    assert i18n.normalise("") == "en"
    assert i18n.normalise("hi") == "hi"

    strings = i18n.ui("fr")
    assert strings["btn_check"] == i18n.UI_EN["btn_check"]

    # And an unknown symptom id must not raise.
    assert i18n.symptom_text("not_a_symptom", "bn")["label"]


def test_translations_actually_differ_from_english():
    """Guards against a table that was copied but never translated."""
    failures = []
    for lang, table in TABLES.items():
        for symptom in ALL_IDS[:20]:
            translated = table.SYMPTOMS[symptom]["label"]
            if translated == i18n.symptom_text(symptom, "en")["label"]:
                failures.append(f"{lang}: {symptom} label is still English")
    assert not failures, "\n".join(failures)


def test_indic_red_flags_are_recognised_offline():
    """The offline path must still catch emergencies in Hindi and Bengali.

    This is the case the Indic table exists for: the LLM is unavailable and
    someone is typing in their own language about something serious.
    """
    cases = [
        ("मुझे सीने में दर्द हो रहा है", "chest_pain"),
        ("seene mein dard ho raha hai", "chest_pain"),
        ("আমার বুকে ব্যথা হচ্ছে", "chest_pain"),
        ("buke betha hocche", "chest_pain"),
        ("साँस लेने में तकलीफ हो रही है", "difficulty_breathing"),
        ("শ্বাস নিতে কষ্ট হচ্ছে", "difficulty_breathing"),
        ("बच्चा सुस्त है", "child_lethargy"),
        ("বাচ্চা নেতিয়ে পড়েছে", "child_lethargy"),
        ("तेज बुखार है", "fever"),
        ("প্রচণ্ড জ্বর হয়েছে", "fever"),
    ]
    failures = []
    for text, expected in cases:
        got = extract_indic(text)
        if expected not in got:
            failures.append(f"{text!r} -> {got}, expected {expected}")
    assert not failures, "\n".join(failures)


def test_indic_pass_ignores_english():
    """English input must not be touched by the substring matcher."""
    for text in ["I have chest pain", "my head hurts", "fever and cough"]:
        assert extract_indic(text) == [], text


def test_indic_phrases_name_real_symptoms():
    unknown = sorted(set(RED_FLAG_PHRASES) - set(ALL_IDS))
    assert not unknown, f"Indic phrases for symptoms that do not exist: {unknown}"


def test_crisis_is_caught_in_every_language():
    """Self-harm must reach the counselling path whatever language it is in.

    This is the single most important multilingual case in the app. Before the
    Indic table existed, someone writing "আমি মরে যেতে চাই" — "I want to die" —
    got a shrug, because the English phrase list cannot match a word of it.
    """
    cases = [
        "I want to end my life",
        "मैं मरना चाहता हूँ",
        "मुझे आत्महत्या के ख्याल आ रहे हैं",
        "main marna chahta hoon",
        "আমি মরে যেতে চাই",
        "আমি আত্মহত্যা করতে চাই",
        "ami more jete chai",
    ]
    failures = [text for text in cases if not check_crisis(text)]
    assert not failures, f"crisis not detected: {failures}"


def test_crisis_does_not_fire_on_ordinary_indic_complaints():
    for text in ["আমার মাথা ব্যথা করছে", "मुझे बुखार है", "পেটে ব্যথা"]:
        assert not check_crisis(text), text


def test_emergency_override_works_in_every_language():
    cases = [
        "my father collapsed and is not responding",
        "पापा बेहोश हो गए हैं",
        "वो साँस नहीं ले रहा",
        "बच्चे ने जहर खा लिया",
        "বাবা অজ্ঞান হয়ে গেছে",
        "শ্বাস নিচ্ছে না",
        "অনেক রক্ত পড়ছে",
    ]
    failures = [text for text in cases if check_emergency_override(text) is None]
    assert not failures, f"emergency not detected: {failures}"


def test_emergency_override_does_not_fire_on_mild_indic_complaints():
    for text in ["हल्का सिरदर्द है", "সামান্য জ্বর", "গলা ব্যথা করছে"]:
        assert check_emergency_override(text) is None, text


if __name__ == "__main__":
    passed = failed = 0
    checks = [
        test_every_symptom_is_translated,
        test_no_translations_for_symptoms_that_do_not_exist,
        test_ui_strings_are_complete,
        test_every_rule_reason_is_translated,
        test_reason_templates_keep_their_placeholder,
        test_context_notes_are_translated,
        test_age_notes_keep_their_placeholder,
        test_safety_critical_strings_are_translated,
        test_levels_specialties_systems_and_contacts_are_translated,
        test_unknown_language_falls_back_to_english,
        test_translations_actually_differ_from_english,
        test_indic_red_flags_are_recognised_offline,
        test_indic_pass_ignores_english,
        test_indic_phrases_name_real_symptoms,
        test_crisis_is_caught_in_every_language,
        test_crisis_does_not_fire_on_ordinary_indic_complaints,
        test_emergency_override_works_in_every_language,
        test_emergency_override_does_not_fire_on_mild_indic_complaints,
    ]
    for check in checks:
        try:
            check()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL | {check.__name__}\n       {exc}")
        else:
            passed += 1
            print(f"PASS | {check.__name__}")

    print(f"\n{passed} passed, {failed} failed")
