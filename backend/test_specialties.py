"""Specialty routing and doctor directory tests. Run: python test_specialties.py"""

import doctors
from specialties import (
    MAX_SUGGESTIONS,
    SPECIALTIES,
    SYMPTOM_OVERRIDES,
    SYSTEM_TO_SPECIALTY,
    recommend,
    specialty_for,
)
from symptoms import ALL_IDS, BY_ID, SYSTEMS

# (symptoms, urgency, specialty that must be suggested first)
ROUTING_CASES = [
    (["chest_pain"], "emergency", "emergency_medicine"),
    (["palpitations"], "urgent_care", "cardiology"),
    (["joint_pain", "back_pain"], "self_care", "orthopaedics"),
    (["toothache"], "self_care", "dentistry"),
    (["ear_pain"], "self_care", "ent"),
    (["red_eye"], "self_care", "ophthalmology"),
    (["rash", "itching"], "self_care", "dermatology"),
    (["missed_period"], "self_care", "gynaecology"),
    (["child_lethargy"], "emergency", "emergency_medicine"),
    (["low_mood", "insomnia"], "self_care", "psychiatry"),
    (["painful_urination"], "urgent_care", "urology"),
    (["diarrhea", "nausea"], "urgent_care", "gastroenterology"),
    (["cough", "sputum"], "self_care", "pulmonology"),
    # Overrides: the body part and the right specialist do not line up.
    (["leg_swelling"], "urgent_care", "cardiology"),
    (["injury_fracture"], "emergency", "emergency_medicine"),
    # Nothing recognised still has to point somewhere.
    ([], "unknown", "general_medicine"),
]


def test_routing():
    failures = []
    for symptoms, level, expected_first in ROUTING_CASES:
        suggested = recommend(symptoms, level)
        if not suggested:
            failures.append(f"{symptoms} ({level}) -> no specialty suggested")
            continue
        if suggested[0]["id"] != expected_first:
            failures.append(
                f"{symptoms} ({level}) -> first was {suggested[0]['id']!r}, "
                f"expected {expected_first!r}"
            )
    assert not failures, "\n".join(failures)


def test_emergency_always_leads_with_emergency_medicine():
    """An emergency result must never lead with an outpatient specialty.

    Telling someone with stroke signs to see a neurologist would send them to
    book an appointment instead of calling an ambulance.
    """
    failures = []
    for symptom in ALL_IDS:
        suggested = recommend([symptom], "emergency")
        if not suggested or suggested[0]["id"] != "emergency_medicine":
            got = suggested[0]["id"] if suggested else "nothing"
            failures.append(f"{symptom} at emergency led with {got}")
    assert not failures, "\n".join(failures)


def test_crisis_returns_mental_health_only():
    """A crisis result must not offer a menu of specialties to choose from."""
    suggested = recommend([], "crisis")
    assert [s["id"] for s in suggested] == ["psychiatry"], suggested


def test_every_symptom_routes_somewhere():
    """No symptom may route to a specialty that does not exist."""
    failures = []
    for symptom in ALL_IDS:
        specialty = specialty_for(symptom)
        if specialty not in SPECIALTIES:
            failures.append(f"{symptom} routes to unknown specialty {specialty!r}")
    assert not failures, "\n".join(failures)


def test_every_system_has_a_specialty():
    """Adding a body system to symptoms.py must not leave it unrouted."""
    missing = [s for s in SYSTEMS if s not in SYSTEM_TO_SPECIALTY]
    assert not missing, f"body systems with no specialty: {missing}"

    unknown = {
        system: specialty
        for system, specialty in SYSTEM_TO_SPECIALTY.items()
        if specialty not in SPECIALTIES
    }
    assert not unknown, f"systems routing to unknown specialties: {unknown}"


def test_overrides_are_live():
    """An override for a symptom that no longer exists is dead configuration.

    It is also actively misleading: it reads as though a routing decision was
    made when nothing consults it.
    """
    stale = [s for s in SYMPTOM_OVERRIDES if s not in BY_ID]
    assert not stale, f"overrides for symptoms that do not exist: {stale}"

    redundant = [
        symptom
        for symptom, specialty in SYMPTOM_OVERRIDES.items()
        if symptom in BY_ID
        and SYSTEM_TO_SPECIALTY.get(BY_ID[symptom].system) == specialty
    ]
    assert not redundant, f"overrides that match the system default anyway: {redundant}"


def test_suggestions_are_capped_and_unique():
    failures = []
    # Something from every system at once — the widest possible input.
    everything = ALL_IDS
    for level in ("emergency", "urgent_care", "self_care", "unknown"):
        suggested = recommend(everything, level)
        ids = [s["id"] for s in suggested]
        if len(ids) > MAX_SUGGESTIONS:
            failures.append(f"{level}: {len(ids)} suggestions exceeds {MAX_SUGGESTIONS}")
        if len(ids) != len(set(ids)):
            failures.append(f"{level}: duplicate suggestions {ids}")
    assert not failures, "\n".join(failures)


def test_placeholder_directory_is_flagged():
    """The shipped directory is sample data and must say so.

    If this ever fails while doctors.json is absent, the frontend would present
    unusable phone numbers as though they were real contacts.
    """
    listed = doctors.all_doctors()
    assert listed, "directory is empty — not even placeholders were generated"

    for doctor in listed:
        assert doctor["specialty"] in SPECIALTIES, doctor
        assert doctor["name"], doctor

    if doctors.using_placeholders():
        unflagged = [d["name"] for d in listed if not d.get("is_placeholder")]
        assert not unflagged, f"placeholder directory has unflagged entries: {unflagged}"


def test_every_specialty_has_someone_listed():
    """A specialty the app recommends but lists nobody for is a dead end."""
    counts = doctors.counts_by_specialty()
    empty = [s for s in SPECIALTIES if counts.get(s, 0) == 0]
    assert not empty, f"specialties with no doctors listed: {empty}"


if __name__ == "__main__":
    passed = failed = 0

    print("--- routing ---")
    for symptoms, level, expected_first in ROUTING_CASES:
        suggested = recommend(symptoms, level)
        got = suggested[0]["id"] if suggested else "nothing"
        ok = got == expected_first
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        names = ", ".join(s["name"] for s in suggested)
        print(f"{'PASS' if ok else 'FAIL'} | {symptoms} ({level}) -> {names}")
        if not ok:
            print(f"       expected {expected_first} first, got {got}")

    print("\n--- invariants ---")
    for check in (
        test_emergency_always_leads_with_emergency_medicine,
        test_crisis_returns_mental_health_only,
        test_every_symptom_routes_somewhere,
        test_every_system_has_a_specialty,
        test_overrides_are_live,
        test_suggestions_are_capped_and_unique,
        test_placeholder_directory_is_flagged,
        test_every_specialty_has_someone_listed,
    ):
        try:
            check()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL | {check.__name__}\n       {exc}")
        else:
            passed += 1
            print(f"PASS | {check.__name__}")

    print(f"\n{passed} passed, {failed} failed")
