"""Opening hours: is this doctor available right now, and if not, when?

"Open now" is the second most useful thing to know about a doctor after "how
far away", and it is the one the existing free-text `timings` field could not
answer -- "Mon–Sat, 10:00–17:00" is readable by a human and opaque to code.

Shape of the data
-----------------
    "hours": {
        "mon": [["10:00", "13:00"], ["17:00", "20:00"]],
        "tue": [["10:00", "13:00"], ["17:00", "20:00"]],
        ...
        "sun": []
    }

A list of intervals per day, because split morning and evening clinics are the
norm in India rather than the exception, and a single open-close pair would
report a doctor as available through a three-hour lunch break. An empty list
means closed that day; a missing day means the same.

    "hours": {"always_open": true}

for emergency departments.

Timezone
--------
Everything is evaluated in the server's local time. That is correct when the
server and the patients are in the same region, which is the case this app is
built for, and wrong for a hosted deployment serving several time zones. Fixing
it properly means storing a timezone per doctor; until there is a reason to,
this stays simple and documented rather than half-solved.

Never trusted blindly: every value is validated on the way in, and anything
malformed makes the doctor "hours unknown" rather than crashing a page or, far
worse, silently reporting a closed clinic as open.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Order matters: index 0 must line up with datetime.weekday() == 0 (Monday).
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_TIME_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

# Statuses are returned as keys rather than sentences so i18n.py can translate
# them. Anything user-visible in this app has to work in three languages.
STATUS_ALWAYS_OPEN = "always_open"
STATUS_OPEN = "open_now"
STATUS_CLOSED = "closed_now"
STATUS_UNKNOWN = "hours_unknown"


def _parse_time(value) -> Optional[int]:
    """"HH:MM" as minutes past midnight, or None if it is not a valid time."""
    if not isinstance(value, str):
        return None
    match = _TIME_PATTERN.match(value.strip())
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def _format_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def normalise(raw) -> Optional[Dict]:
    """Validate an hours block, or return None if it is unusable.

    Returns either {"always_open": True} or {day: [(start, end), ...]} with
    times as minutes past midnight. Invalid intervals are dropped individually
    rather than rejecting the whole doctor -- one typo in Thursday's hours
    should not hide a clinic from the directory.
    """
    if not isinstance(raw, dict):
        return None

    if raw.get("always_open") is True:
        return {"always_open": True}

    parsed: Dict[str, List] = {}
    for day in DAYS:
        intervals = raw.get(day) or []
        if not isinstance(intervals, list):
            continue

        day_intervals = []
        for interval in intervals:
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                continue
            start, end = _parse_time(interval[0]), _parse_time(interval[1])
            if start is None or end is None or start >= end:
                # Zero-length and backwards intervals are dropped. A clinic
                # "open" from 17:00 to 09:00 is a data entry mistake, and
                # guessing it meant overnight could report it open all night.
                continue
            day_intervals.append((start, end))

        if day_intervals:
            parsed[day] = sorted(day_intervals)

    return parsed or None


def status(hours: Optional[Dict], now: Optional[datetime] = None) -> Dict:
    """Whether a doctor is open, as a translatable key plus parameters.

    `now` is injectable so tests do not depend on when they are run -- a test
    suite that passes only during clinic hours is worse than no test.
    """
    if not hours:
        return {"status": STATUS_UNKNOWN, "open": False, "params": {}}

    if hours.get("always_open"):
        return {"status": STATUS_ALWAYS_OPEN, "open": True, "params": {}}

    now = now or datetime.now()
    today = DAYS[now.weekday()]
    minutes_now = now.hour * 60 + now.minute

    for start, end in hours.get(today, []):
        if start <= minutes_now < end:
            return {
                "status": STATUS_OPEN,
                "open": True,
                "params": {"until": _format_time(end)},
            }

    opens = next_opening(hours, now)
    return {
        "status": STATUS_CLOSED,
        "open": False,
        "params": {"opens": opens} if opens else {},
    }


def next_opening(hours: Optional[Dict], now: Optional[datetime] = None) -> Optional[str]:
    """When this doctor next opens, e.g. "17:00" or "Mon 10:00".

    Looks a week ahead and gives up after that: a doctor with no opening in the
    next seven days is closed in any sense the patient cares about.
    """
    if not hours or hours.get("always_open"):
        return None

    now = now or datetime.now()
    minutes_now = now.hour * 60 + now.minute

    for offset in range(8):
        day_date = now + timedelta(days=offset)
        day = DAYS[day_date.weekday()]
        for start, _ in hours.get(day, []):
            if offset == 0 and start <= minutes_now:
                continue
            if offset == 0:
                return _format_time(start)
            if offset == 1:
                return f"tomorrow {_format_time(start)}"
            return f"{day.capitalize()} {_format_time(start)}"

    return None


def describe(hours: Optional[Dict]) -> str:
    """A short human-readable summary, for directories that have no `timings`.

    Consecutive days with identical hours are grouped, so a normal week reads
    "Mon–Sat 10:00–13:00, 17:00–20:00" rather than six near-identical lines.
    """
    if not hours:
        return ""
    if hours.get("always_open"):
        return "Open 24 hours"

    # Group consecutive days that share the same intervals.
    groups = []
    for day in DAYS:
        intervals = hours.get(day, [])
        if not intervals:
            continue
        signature = tuple(intervals)
        if groups and groups[-1][2] == signature and DAYS.index(day) == DAYS.index(groups[-1][1]) + 1:
            groups[-1][1] = day
        else:
            groups.append([day, day, signature])

    parts = []
    for first, last, intervals in groups:
        span = first.capitalize() if first == last else f"{first.capitalize()}–{last.capitalize()}"
        times = ", ".join(f"{_format_time(s)}–{_format_time(e)}" for s, e in intervals)
        parts.append(f"{span} {times}")
    return "; ".join(parts)
