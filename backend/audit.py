"""Append-only record of every triage decision.

Why this exists
---------------
Medical software has to be able to answer "why did it say that, on that day?"
long after the rules have moved on. Without a record, a triage result is an
event that happened once and left no trace: it cannot be reviewed by a
clinician, reproduced by an engineer, or defended to anyone asking whether the
app behaved reasonably.

So every graded result is written here with the version stamps that produced it
(see version.py). Those two modules only mean something together -- the record
says what was decided, the stamps say which logic decided it.

Append-only, deliberately
-------------------------
There is no update and no delete of individual rows in this module's API. An
audit trail that can be edited after the fact answers a weaker question than
one that cannot. The single exception is `purge_before`, which deletes whole
date ranges to honour a retention policy: that is data protection, not
revision, and it removes records wholesale rather than altering what any
surviving record says.

What is deliberately not stored
-------------------------------
No name, no phone number, no IP address, no browser fingerprint, no account.
Nothing here identifies a person, because nothing needs to: the questions this
log exists to answer are about the *app's* behaviour, not about individuals.

Exact age is reduced to a band for the same reason. The rules only care about
which band someone falls in, so storing "70-79" instead of "73" loses nothing
the app uses while removing a field that helps re-identify a person in a small
city.

The free text is kept, because it is the one thing a clinical reviewer cannot
work without -- "the app failed to understand this" is unactionable unless the
log says what "this" was. That makes audit.db health data: it is git-ignored,
it should live on an encrypted disk, and `purge_before` should run on a
schedule. Those are deployment decisions this module cannot make for you.

Never breaks triage
-------------------
Every function here swallows its own errors after logging them. A failed write
must never take down the endpoint it is recording: an app that stops giving
someone urgency advice because a disk is full has failed at the only thing that
actually matters. The log degrades; the triage does not.
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_HERE, "audit.db")

# Serialises writes from FastAPI's thread pool. SQLite handles concurrent
# readers, but concurrent writers raise "database is locked" under load, and a
# lock here is cheaper than teaching every caller to retry.
_write_lock = threading.Lock()

_initialised = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS triage_events (
    id                  TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    lang                TEXT NOT NULL,
    input_text          TEXT NOT NULL,
    symptoms            TEXT NOT NULL,
    symptom_count       INTEGER NOT NULL,
    extraction_source   TEXT NOT NULL,
    urgency_level       TEXT NOT NULL,
    level_before_context TEXT,
    safety_note         TEXT,
    context_notes       TEXT,
    age_band            TEXT,
    duration            TEXT,
    recognised          INTEGER NOT NULL,
    app_version         TEXT NOT NULL,
    ruleset_version     TEXT NOT NULL,
    vocabulary_version  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_created_at  ON triage_events (created_at);
CREATE INDEX IF NOT EXISTS idx_recognised  ON triage_events (recognised);
CREATE INDEX IF NOT EXISTS idx_urgency     ON triage_events (urgency_level);
CREATE INDEX IF NOT EXISTS idx_ruleset     ON triage_events (ruleset_version);
"""

# Bands rather than exact ages. These match the thresholds context.py actually
# applies, so banding costs the log nothing it would otherwise have used.
AGE_BANDS = [
    (1, "under_1"),
    (5, "1_4"),
    (13, "5_12"),
    (18, "13_17"),
    (40, "18_39"),
    (65, "40_64"),
    (80, "65_79"),
    (200, "80_plus"),
]


def band_age(age: Optional[int]) -> Optional[str]:
    """An age band, or None when no age was given."""
    if age is None:
        return None
    for ceiling, label in AGE_BANDS:
        if age < ceiling:
            return label
    return "80_plus"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_FILE, timeout=5.0)
    # WAL lets readers work while a write is in flight, which matters because
    # the reporting queries below run against a live database.
    connection.execute("PRAGMA journal_mode=WAL")
    connection.row_factory = sqlite3.Row
    return connection


def init() -> bool:
    """Create the database if it is not there. Safe to call repeatedly."""
    global _initialised
    if _initialised:
        return True
    try:
        with _write_lock, _connect() as connection:
            connection.executescript(SCHEMA)
        _initialised = True
        return True
    except sqlite3.Error as exc:
        log.warning("Could not initialise audit database (%s) — auditing off.", exc)
        return False


def record(
    *,
    input_text: str,
    lang: str,
    symptoms: List[str],
    extraction_source: str,
    urgency_level: str,
    versions: Dict[str, str],
    level_before_context: Optional[str] = None,
    safety_note: Optional[str] = None,
    context_notes: Optional[List[str]] = None,
    age: Optional[int] = None,
    duration: Optional[str] = None,
) -> Optional[str]:
    """Write one triage decision. Returns its id, or None if the write failed.

    Keyword-only because this has fourteen fields and several are adjacent
    strings -- positional calls would eventually swap `urgency_level` with
    `extraction_source` and nobody would notice, since both are short lowercase
    words that look plausible in either slot.
    """
    if not init():
        return None

    event_id = uuid.uuid4().hex
    try:
        with _write_lock, _connect() as connection:
            connection.execute(
                """
                INSERT INTO triage_events (
                    id, created_at, lang, input_text, symptoms, symptom_count,
                    extraction_source, urgency_level, level_before_context,
                    safety_note, context_notes, age_band, duration, recognised,
                    app_version, ruleset_version, vocabulary_version
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event_id,
                    datetime.now(timezone.utc).isoformat(),
                    lang,
                    input_text,
                    json.dumps(symptoms),
                    len(symptoms),
                    extraction_source,
                    urgency_level,
                    level_before_context,
                    safety_note,
                    json.dumps(context_notes or []),
                    band_age(age),
                    duration,
                    1 if symptoms else 0,
                    versions.get("app", ""),
                    versions.get("ruleset", ""),
                    versions.get("vocabulary", ""),
                ),
            )
        return event_id
    except sqlite3.Error as exc:
        # Logged, not raised. See the module docstring: the triage result must
        # still reach the person waiting for it.
        log.warning("Could not write audit record (%s).", exc)
        return None


def get(event_id: str) -> Optional[Dict]:
    """One recorded decision, or None."""
    if not init():
        return None
    try:
        with _connect() as connection:
            row = connection.execute(
                "SELECT * FROM triage_events WHERE id = ?", (event_id,)
            ).fetchone()
    except sqlite3.Error as exc:
        log.warning("Could not read audit record (%s).", exc)
        return None

    if row is None:
        return None

    event = dict(row)
    event["symptoms"] = json.loads(event["symptoms"])
    event["context_notes"] = json.loads(event["context_notes"])
    event["recognised"] = bool(event["recognised"])
    return event


def unrecognised(limit: int = 100) -> List[Dict]:
    """Inputs the app could not read, newest first.

    The most useful query in this module. Every row is a real person who
    described a real problem in words the vocabulary does not contain, and each
    one is a concrete instruction about which phrase to add next.
    """
    if not init():
        return []
    try:
        with _connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, lang, input_text, vocabulary_version
                FROM triage_events
                WHERE recognised = 0
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        log.warning("Could not read unrecognised inputs (%s).", exc)
        return []


def statistics() -> Dict:
    """Counts for the /audit/stats endpoint."""
    if not init():
        return {"available": False}
    try:
        with _connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM triage_events"
            ).fetchone()[0]
            unread = connection.execute(
                "SELECT COUNT(*) FROM triage_events WHERE recognised = 0"
            ).fetchone()[0]
            by_level = connection.execute(
                """
                SELECT urgency_level, COUNT(*) AS n
                FROM triage_events GROUP BY urgency_level ORDER BY n DESC
                """
            ).fetchall()
            by_source = connection.execute(
                """
                SELECT extraction_source, COUNT(*) AS n
                FROM triage_events GROUP BY extraction_source ORDER BY n DESC
                """
            ).fetchall()
            rulesets = connection.execute(
                "SELECT COUNT(DISTINCT ruleset_version) FROM triage_events"
            ).fetchone()[0]
    except sqlite3.Error as exc:
        log.warning("Could not read audit statistics (%s).", exc)
        return {"available": False}

    return {
        "available": True,
        "total_events": total,
        "unrecognised": unread,
        # The number that matters most for improving the vocabulary: what share
        # of real users the app simply did not understand.
        "unrecognised_rate": round(unread / total, 4) if total else 0.0,
        "by_urgency": {row["urgency_level"]: row["n"] for row in by_level},
        "by_extraction_source": {row["extraction_source"]: row["n"] for row in by_source},
        "distinct_rulesets_seen": rulesets,
    }


def purge_before(cutoff_days: int) -> int:
    """Delete records older than `cutoff_days`. Returns how many went.

    The only deletion this module allows, and it is whole-record and
    date-ranged on purpose -- a retention policy, not a way to revise history.
    Run it on a schedule; free text about someone's health should not be kept
    indefinitely because nobody chose a number.
    """
    if not init():
        return 0
    if cutoff_days < 0:
        raise ValueError("cutoff_days must not be negative")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=cutoff_days)).isoformat()
    try:
        with _write_lock, _connect() as connection:
            cursor = connection.execute(
                "DELETE FROM triage_events WHERE created_at < ?", (cutoff,)
            )
            return cursor.rowcount
    except sqlite3.Error as exc:
        log.warning("Could not purge audit records (%s).", exc)
        return 0
