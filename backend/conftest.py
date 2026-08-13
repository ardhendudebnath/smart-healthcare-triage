"""Shared pytest setup.

Keeps the test suite out of the real audit database.

test_main.py exercises the live FastAPI app, and every /triage call it makes
writes a row exactly as a real request would. Without this, running the suite
files invented complaints -- "asdf qwerty", "he is unconscious" -- into
backend/audit.db alongside genuine ones.

That matters more than ordinary test-pollution. The audit trail is the record a
clinical reviewer would read and the source of the unrecognised-input list used
to decide which phrases to add next; test fixtures mixed into it corrupt both,
and there is no field distinguishing a real entry from a synthetic one after the
fact. It also inflates /audit/stats, so the unrecognised rate -- the number that
says how often the app fails to understand a real person -- silently measures
the test suite instead.

Session-scoped and automatic, so no test has to remember. test_audit.py points
DB_FILE at its own temporary file per test and is unaffected by this.
"""

import os
import tempfile

import pytest

import audit


@pytest.fixture(autouse=True, scope="session")
def _isolate_audit_database():
    directory = tempfile.mkdtemp(prefix="triage-test-audit-")
    original = audit.DB_FILE

    audit.DB_FILE = os.path.join(directory, "audit.db")
    audit._initialised = False

    yield

    audit.DB_FILE = original
    audit._initialised = False
    for name in os.listdir(directory):
        try:
            os.unlink(os.path.join(directory, name))
        except OSError:
            pass
    try:
        os.rmdir(directory)
    except OSError:
        pass
