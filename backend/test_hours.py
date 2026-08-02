"""Opening-hours tests. Run: python test_hours.py

Every check passes an explicit `now`. A test suite whose result depends on when
it is run is worse than no suite: it fails at 3am for reasons nobody can
reproduce during the day.
"""

from datetime import datetime

import doctors
from hours import (
    STATUS_ALWAYS_OPEN,
    STATUS_CLOSED,
    STATUS_OPEN,
    STATUS_UNKNOWN,
    describe,
    next_opening,
    normalise,
    status,
)

# A clinic with separate morning and evening sittings — the normal pattern in
# India, and the one a single open/close pair gets wrong.
SPLIT_SHIFT = normalise(
    {
        "mon": [["10:00", "13:00"], ["17:00", "20:00"]],
        "tue": [["10:00", "13:00"], ["17:00", "20:00"]],
        "wed": [["10:00", "13:00"], ["17:00", "20:00"]],
        "thu": [["10:00", "13:00"], ["17:00", "20:00"]],
        "fri": [["10:00", "13:00"], ["17:00", "20:00"]],
        "sat": [["10:00", "14:00"]],
        "sun": [],
    }
)

ALWAYS = normalise({"always_open": True})

# 2026-08-03 is a Monday, which keeps the weekday arithmetic below readable.
MON = lambda h, m=0: datetime(2026, 8, 3, h, m)   # noqa: E731
SAT = lambda h, m=0: datetime(2026, 8, 8, h, m)   # noqa: E731
SUN = lambda h, m=0: datetime(2026, 8, 9, h, m)   # noqa: E731

CASES = [
    # (label, hours, now, expected status)
    ("Monday mid-morning", SPLIT_SHIFT, MON(11), STATUS_OPEN),
    # The whole reason intervals are a list: a single pair would call this open.
    ("Monday lunch break", SPLIT_SHIFT, MON(14), STATUS_CLOSED),
    ("Monday evening sitting", SPLIT_SHIFT, MON(18), STATUS_OPEN),
    ("Monday before opening", SPLIT_SHIFT, MON(8), STATUS_CLOSED),
    ("Monday after closing", SPLIT_SHIFT, MON(21), STATUS_CLOSED),
    # Boundaries: open at the opening minute, closed at the closing minute.
    ("exactly at opening", SPLIT_SHIFT, MON(10, 0), STATUS_OPEN),
    ("one minute before closing", SPLIT_SHIFT, MON(12, 59), STATUS_OPEN),
    ("exactly at closing", SPLIT_SHIFT, MON(13, 0), STATUS_CLOSED),
    ("Saturday short day", SPLIT_SHIFT, SAT(11), STATUS_OPEN),
    ("Saturday evening (closed)", SPLIT_SHIFT, SAT(18), STATUS_CLOSED),
    ("Sunday", SPLIT_SHIFT, SUN(11), STATUS_CLOSED),
    # Emergency departments.
    ("emergency at 3am", ALWAYS, MON(3), STATUS_ALWAYS_OPEN),
    ("emergency on Sunday", ALWAYS, SUN(4), STATUS_ALWAYS_OPEN),
    # No data at all.
    ("no hours given", None, MON(11), STATUS_UNKNOWN),
]


def test_status():
    failures = []
    for label, hours_data, now, expected in CASES:
        got = status(hours_data, now)["status"]
        if got != expected:
            failures.append(f"{label}: got {got}, expected {expected}")
    assert not failures, "\n".join(failures)


def test_open_flag_matches_status():
    """`open` and `status` must never disagree.

    The frontend sorts on one and displays the other; if they diverge a clinic
    shows a "Closed" badge at the top of an "open now" list.
    """
    failures = []
    for label, hours_data, now, expected in CASES:
        result = status(hours_data, now)
        should_be_open = result["status"] in (STATUS_OPEN, STATUS_ALWAYS_OPEN)
        if result["open"] != should_be_open:
            failures.append(f"{label}: open={result['open']} but status={result['status']}")
    assert not failures, "\n".join(failures)


def test_next_opening():
    # During the lunch break, the next opening is the evening sitting.
    assert next_opening(SPLIT_SHIFT, MON(14)) == "17:00"
    # Before opening, it is this morning.
    assert next_opening(SPLIT_SHIFT, MON(8)) == "10:00"
    # After the evening sitting, it is the next day.
    assert next_opening(SPLIT_SHIFT, MON(21)).startswith("tomorrow")
    # Sunday closed — next opening is Monday.
    assert next_opening(SPLIT_SHIFT, SUN(11)).startswith("tomorrow")
    # Always-open has no "next" opening.
    assert next_opening(ALWAYS, MON(3)) is None


def test_closed_status_says_when_it_opens():
    """A "Closed" badge with no reopening time is a dead end for the patient."""
    result = status(SPLIT_SHIFT, MON(14))
    assert result["status"] == STATUS_CLOSED
    assert result["params"].get("opens") == "17:00"


def test_open_status_says_when_it_closes():
    result = status(SPLIT_SHIFT, MON(11))
    assert result["params"].get("until") == "13:00"


def test_normalise_rejects_junk_without_raising():
    """Bad data must degrade to "hours unknown", never to a crash or a lie."""
    assert normalise(None) is None
    assert normalise("Mon-Fri 9-5") is None
    assert normalise({}) is None
    assert normalise({"mon": "10:00-13:00"}) is None      # not a list
    assert normalise({"mon": [["25:00", "26:00"]]}) is None  # impossible times
    assert normalise({"mon": [["10:00"]]}) is None        # missing end
    assert normalise({"xyz": [["10:00", "11:00"]]}) is None  # unknown day

    # A backwards interval is dropped rather than guessed at. Reading
    # 17:00–09:00 as "overnight" would report a closed clinic as open all night.
    assert normalise({"mon": [["17:00", "09:00"]]}) is None

    # One bad day must not discard the good ones.
    partial = normalise({"mon": [["10:00", "13:00"]], "tue": [["bad", "worse"]]})
    assert partial and "mon" in partial and "tue" not in partial


def test_describe_groups_consecutive_days():
    text = describe(SPLIT_SHIFT)
    assert "Mon–Fri" in text, text
    assert "Sat" in text, text
    assert "Sun" not in text, text
    assert describe(ALWAYS) == "Open 24 hours"
    assert describe(None) == ""


def test_directory_entries_carry_usable_hours():
    """Every placeholder must produce a real status, not "unknown".

    The badges cannot be seen working — or seen to be broken — if the shipped
    directory has no hours at all.
    """
    failures = []
    for doctor in doctors.all_doctors():
        result = status(doctor.get("hours"), MON(11))
        if result["status"] == STATUS_UNKNOWN:
            failures.append(doctor["name"])
    assert not failures, f"doctors with unusable hours: {failures[:5]}"


def test_emergency_placeholders_are_always_open():
    for doctor in doctors.for_specialty("emergency_medicine"):
        result = status(doctor.get("hours"), SUN(3))
        assert result["open"], f"{doctor['name']} closed at 3am on a Sunday"


def test_coordinates_are_both_or_neither():
    """Half a coordinate would place a clinic in the Atlantic."""
    entry = doctors._normalise(
        {"name": "Dr Test", "specialty": "cardiology", "lat": 22.57}, 1
    )
    assert entry["lat"] is None and entry["lng"] is None

    good = doctors._normalise(
        {"name": "Dr Test", "specialty": "cardiology", "lat": 22.57, "lng": 88.36}, 1
    )
    assert good["lat"] == 22.57 and good["lng"] == 88.36

    # Out of range and junk are both discarded.
    for bad in ({"lat": 999, "lng": 88.36}, {"lat": "north", "lng": "east"}):
        entry = doctors._normalise({"name": "D", "specialty": "cardiology", **bad}, 1)
        assert entry["lat"] is None and entry["lng"] is None, bad


if __name__ == "__main__":
    passed = failed = 0

    print("--- open / closed ---")
    for label, hours_data, now, expected in CASES:
        got = status(hours_data, now)
        ok = got["status"] == expected
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
        extra = got["params"].get("until") or got["params"].get("opens") or ""
        print(f"{'PASS' if ok else 'FAIL'} | {label:<28} {got['status']} {extra}")
        if not ok:
            print(f"       expected {expected}")

    print("\n--- invariants ---")
    for check in (
        test_open_flag_matches_status,
        test_next_opening,
        test_closed_status_says_when_it_opens,
        test_open_status_says_when_it_closes,
        test_normalise_rejects_junk_without_raising,
        test_describe_groups_consecutive_days,
        test_directory_entries_carry_usable_hours,
        test_emergency_placeholders_are_always_open,
        test_coordinates_are_both_or_neither,
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
