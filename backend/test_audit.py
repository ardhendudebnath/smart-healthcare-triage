"""Audit trail and version stamp tests.

Run: python -m pytest test_audit.py

Every test points `audit.DB_FILE` at a temporary database. A test suite that
writes to the real audit.db would both pollute a medical record and make its own
assertions depend on whatever happened to be in there already.
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

import audit
import version


@pytest.fixture(autouse=True)
def temp_database(monkeypatch):
    """Point the module at a throwaway database for each test."""
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    os.unlink(path)  # sqlite creates it; an existing empty file is not a db

    monkeypatch.setattr(audit, "DB_FILE", path)
    monkeypatch.setattr(audit, "_initialised", False)
    yield path

    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except OSError:
            pass


def _record(**overrides):
    payload = {
        "input_text": "I have chest pain",
        "lang": "en",
        "symptoms": ["chest_pain"],
        "extraction_source": "offline",
        "urgency_level": "emergency",
        "versions": version.stamp(),
    }
    payload.update(overrides)
    return audit.record(**payload)


# --- version stamps -------------------------------------------------------

def test_stamp_has_all_three_versions():
    stamp = version.stamp()
    assert set(stamp) == {"app", "ruleset", "vocabulary"}
    assert all(stamp.values()), stamp


def test_versions_are_stable_across_calls():
    """A version that changes when nothing changed is worse than none at all.

    Sets and dicts have no guaranteed iteration order, so a naive hash of the
    rule tables would drift between calls and make every audit row look like it
    came from different logic.
    """
    assert version.stamp() == version.stamp()
    assert version._ruleset_version() == version._ruleset_version()
    assert version._vocabulary_version() == version._vocabulary_version()


def test_ruleset_and_vocabulary_versions_are_independent():
    """Adding a phrase must not look like a change to how results are graded."""
    assert version.RULESET_VERSION != version.VOCABULARY_VERSION


def test_version_changes_when_a_rule_changes(monkeypatch):
    """The whole point: edit the rules and the stamp must follow."""
    before = version._ruleset_version()
    monkeypatch.setattr(
        version, "EMERGENCY_SINGLE", version.EMERGENCY_SINGLE | {"invented_symptom"}
    )
    assert version._ruleset_version() != before


# --- recording ------------------------------------------------------------

def test_record_returns_an_id_and_stores_the_decision():
    event_id = _record()
    assert event_id

    event = audit.get(event_id)
    assert event["urgency_level"] == "emergency"
    assert event["symptoms"] == ["chest_pain"]
    assert event["input_text"] == "I have chest pain"
    assert event["recognised"] is True
    assert event["ruleset_version"] == version.RULESET_VERSION


def test_missing_event_returns_none():
    assert audit.get("nonexistent") is None


def test_unrecognised_input_is_flagged_and_listed():
    """The query that drives vocabulary improvements."""
    _record(input_text="my wibble hurts", symptoms=[], urgency_level="unknown")
    _record()  # a recognised one, which must not appear below

    entries = audit.unrecognised()
    assert len(entries) == 1
    assert entries[0]["input_text"] == "my wibble hurts"


def test_age_is_stored_as_a_band_not_an_exact_value():
    """Banding is a privacy measure, and costs nothing the rules use."""
    event = audit.get(_record(age=73))
    assert event["age_band"] == "65_79"
    assert "73" not in str(event["age_band"])


@pytest.mark.parametrize(
    "age,expected",
    [
        (0, "under_1"),
        (3, "1_4"),
        (8, "5_12"),
        (15, "13_17"),
        (30, "18_39"),
        (50, "40_64"),
        (70, "65_79"),
        (92, "80_plus"),
        (None, None),
    ],
)
def test_age_bands(age, expected):
    assert audit.band_age(age) == expected


def test_statistics_count_what_matters():
    _record()
    _record(symptoms=[], urgency_level="unknown")

    stats = audit.statistics()
    assert stats["available"] is True
    assert stats["total_events"] == 2
    assert stats["unrecognised"] == 1
    assert stats["unrecognised_rate"] == 0.5
    assert stats["by_urgency"]["emergency"] == 1


def test_statistics_on_an_empty_database_do_not_divide_by_zero():
    stats = audit.statistics()
    assert stats["total_events"] == 0
    assert stats["unrecognised_rate"] == 0.0


# --- retention ------------------------------------------------------------

def test_purge_removes_only_records_past_the_cutoff():
    keep = _record()
    drop = _record()

    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    with audit._connect() as connection:
        connection.execute(
            "UPDATE triage_events SET created_at = ? WHERE id = ?", (old, drop)
        )

    assert audit.purge_before(365) == 1
    assert audit.get(keep) is not None
    assert audit.get(drop) is None


def test_purge_rejects_a_negative_cutoff():
    """A negative cutoff is a future timestamp, which would delete everything."""
    with pytest.raises(ValueError):
        audit.purge_before(-1)


# --- failure behaviour ----------------------------------------------------

def test_a_broken_database_never_raises(monkeypatch):
    """Triage must survive a failing audit log.

    An app that stops giving urgency advice because a disk filled up has failed
    at the only thing that actually matters, so every entry point degrades to a
    falsy return instead of propagating.
    """
    monkeypatch.setattr(audit, "_initialised", False)
    monkeypatch.setattr(audit, "DB_FILE", os.path.join(os.sep, "nope", "x.db"))

    assert _record() is None
    assert audit.get("anything") is None
    assert audit.unrecognised() == []
    assert audit.statistics() == {"available": False}
    assert audit.purge_before(30) == 0
