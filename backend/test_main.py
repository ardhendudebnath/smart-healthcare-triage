"""Endpoint tests. Run: python test_main.py

These run the app in-process through FastAPI's TestClient, so no server needs to
be started.

Extraction is pinned to the offline path throughout. Left alone these tests call
Gemini once per case, which makes them slow, non-deterministic, and dependent on
a third-party API being up — during one run Gemini returned 503s and the suite
spent its time waiting on timeouts instead of testing anything. The LLM's own
failure handling is exercised by that fallback existing at all; what these tests
are for is the endpoint contract around it.
"""

import main
from fastapi.testclient import TestClient

from main import app
from specialties import SPECIALTIES

# Force the deterministic spaCy path. extract_symptoms_llm returning None is
# exactly what main.py already handles on any LLM failure, so this exercises a
# real code path rather than a special test-only one.
main.extract_symptoms_llm = lambda text: None

client = TestClient(app)

LEVELS = {"emergency", "urgent_care", "self_care", "unknown", "crisis"}

# Every key a /triage response must carry, on every path through the endpoint.
# The crisis branch returns early and had drifted out of sync — it was missing
# follow_up_questions, so a client reading that field unconditionally would have
# broken on the one result it can least afford to mishandle. Checked as a set
# rather than per-field so the next key added to one branch and not the other
# fails here instead of in someone's browser.
TRIAGE_KEYS = {
    "event_id",
    "symptoms_detected",
    "symptom_details",
    "urgency_level",
    "message",
    "reason",
    "extraction_source",
    "contacts",
    "recommended_specialties",
    "disclaimer",
    "safety_note",
    "context_notes",
    "follow_up_questions",
    "versions",
    "lang",
}


def _triage(message: str) -> dict:
    response = client.post("/triage", json={"message": message})
    assert response.status_code == 200, response.text
    return response.json()


def test_health_check():
    body = client.get("/").json()
    assert body["status"] == "ok"
    assert body["symptoms_known"] > 0
    assert body["doctors_listed"] > 0


def test_symptom_reference():
    body = client.get("/symptoms").json()
    assert body["total"] > 0
    assert body["systems"]
    for group in body["systems"]:
        assert group["symptoms"], f"{group['id']} has no symptoms"
        for symptom in group["symptoms"]:
            # The whole point of the reference is that nobody sees a raw id.
            assert symptom["label"], symptom
            assert symptom["description"], symptom


def test_doctor_directory_filter():
    body = client.get("/doctors", params={"specialty": "cardiology"}).json()
    assert body["doctors"]
    assert all(d["specialty"] == "cardiology" for d in body["doctors"])

    assert client.get("/doctors", params={"specialty": "nonsense"}).status_code == 404


def test_triage_response_shape():
    body = _triage("I have a headache and a sore throat")
    for field in (
        "symptoms_detected",
        "symptom_details",
        "urgency_level",
        "message",
        "reason",
        "contacts",
        "recommended_specialties",
        "disclaimer",
        "safety_note",
    ):
        assert field in body, f"missing {field}"
    assert body["urgency_level"] in LEVELS
    assert len(body["symptom_details"]) == len(body["symptoms_detected"])


def test_every_result_offers_a_way_to_get_help():
    """No result may leave someone with no contact and no disclaimer.

    Including the ones where extraction failed entirely — a person the app could
    not understand still needs a number to call.
    """
    for message in [
        "I have chest pain",
        "mild headache",
        "asdf qwerty",
        "",
        "I want to end my life",
    ]:
        body = _triage(message)
        assert body["contacts"], f"{message!r} returned no contacts"
        assert body["disclaimer"], f"{message!r} returned no disclaimer"
        assert body["recommended_specialties"], f"{message!r} suggested no specialty"


def test_reason_never_contradicts_the_level():
    """An escalated result must not carry the reason for its old grade.

    The safety overrides raise the urgency after the rules have already run, so
    the rule's explanation goes stale. Left in place it produces the worst kind
    of output: "call an ambulance" directly above "should be seen today".
    """
    for message in [
        "my father collapsed and is not responding",
        "he is unconscious",
        "the worst stomach pain of my life",
        "severe back pain",
    ]:
        body = _triage(message)
        if body["safety_note"]:
            assert not body["reason"], (
                f"{message!r} -> {body['urgency_level']} carries a stale reason: "
                f"{body['reason']!r} alongside {body['safety_note']!r}"
            )


def test_crisis_short_circuits_symptom_analysis():
    body = _triage("I want to kill myself")
    assert body["urgency_level"] == "crisis"
    assert body["symptoms_detected"] == []
    assert body["symptom_details"] == []
    # The counselling line must come first, not the ambulance.
    assert body["contacts"][0]["number"] == "14416"
    assert [s["id"] for s in body["recommended_specialties"]] == ["psychiatry"]


def test_emergency_leads_with_emergency_medicine():
    body = _triage("my father collapsed and is not responding")
    assert body["urgency_level"] == "emergency"
    assert body["recommended_specialties"][0]["id"] == "emergency_medicine"
    assert body["contacts"][0]["number"] == "112"


def test_recommended_specialties_are_real():
    body = _triage("my knee is swollen")
    for specialty in body["recommended_specialties"]:
        assert specialty["id"] in SPECIALTIES, specialty
        assert specialty["name"] and specialty["focus"]


def test_every_triage_path_returns_the_same_shape():
    """The crisis branch returns early, so it can drift without anything failing.

    It did: follow_up_questions was added to the ordinary path and not to this
    one, and every test still passed because each asserted on the fields it
    happened to care about. Only running the app surfaced it.
    """
    paths = {
        "ordinary": "I have a headache",
        "emergency": "chest pain and difficulty breathing",
        "crisis": "I want to end my life",
        "nothing recognised": "I want to book an appointment",
        "override": "my father collapsed and is not responding",
    }
    failures = []
    for label, message in paths.items():
        keys = set(_triage(message))
        if keys != TRIAGE_KEYS:
            missing = sorted(TRIAGE_KEYS - keys)
            extra = sorted(keys - TRIAGE_KEYS)
            failures.append(f"{label}: missing={missing} extra={extra}")
    assert not failures, "\n".join(failures)


def test_crisis_is_never_asked_follow_up_questions():
    """Someone in crisis needs a counsellor's number, not a questionnaire."""
    assert _triage("I want to end my life")["follow_up_questions"] == []


if __name__ == "__main__":
    passed = failed = 0
    checks = [
        test_health_check,
        test_symptom_reference,
        test_doctor_directory_filter,
        test_triage_response_shape,
        test_every_result_offers_a_way_to_get_help,
        test_reason_never_contradicts_the_level,
        test_crisis_short_circuits_symptom_analysis,
        test_emergency_leads_with_emergency_medicine,
        test_recommended_specialties_are_real,
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
