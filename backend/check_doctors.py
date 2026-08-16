"""Check a doctors.json before anyone relies on it.

    python check_doctors.py                    # checks doctors.json
    python check_doctors.py doctors.gbp-agartala.json

Exits non-zero if anything is wrong enough to mislead a patient, so this can go
in a pre-demo checklist or a git hook.

Why this exists
---------------
doctors.py is deliberately forgiving at runtime: a malformed entry is skipped
with a log line and the app keeps serving. That is right for a live service and
wrong for the person filling the file in, who will never see the log and will
assume the entry is live. Every silent skip in doctors.py is a loud error here.

The checks are ordered by what actually hurts:

  ERROR   the entry is silently dropped, or shows a patient something false --
          a number that does not ring, a clinic marked open when it is shut
  WARN    the entry works but is worse than it should be, or a triage result
          leads nowhere
  INFO    counts, for a sense of how complete the directory is
"""

import json
import math
import os
import re
import statistics
import sys
from datetime import datetime
from typing import Dict, List, Tuple

import hours as hours_module
from specialties import SPECIALTIES

DEFAULT_FILE = "doctors.json"

# Rough bounding box for India. Only used to spot coordinates that are the wrong
# way round or left at a template default -- not to reject anywhere outside it,
# since nothing stops this app being pointed at another country.
INDIA_LAT = (6.0, 37.5)
INDIA_LNG = (68.0, 97.5)

# An entry this many times further from the centre than the typical entry, and at
# least OUTLIER_FLOOR_KM away, is worth a human looking at.
#
# Relative rather than a fixed distance, because this tool cannot know the scale
# of the directory it is handed. Fifteen kilometres is a lot for one city and
# nothing for a state, so the check measures each entry against how spread out
# its own neighbours are. The floor stops a tightly clustered directory from
# flagging a hospital two streets further out than the rest.
#
# This exists because of a real near-miss. Looking up IGM Hospital returned
# 23.49, 91.16 -- a confident-looking pair roughly 40 km from Agartala, out past
# the Bangladesh border. It is in India, the right way round, and passes every
# other check in this file. Only its distance from the other entries gives it
# away, which is exactly the failure the directory's own notes warn about: a
# coordinate that is slightly wrong puts a hospital on the wrong road while
# looking perfectly correct.
#
# A first attempt used a flat 150 km and caught nothing, because the bad
# coordinate was only 39 km out. Worth remembering that a threshold nobody has
# tested against a real mistake is decoration.
OUTLIER_RATIO = 3.0
OUTLIER_FLOOR_KM = 25.0

# Text that means "I have not filled this in yet". A card reading "Add hospital
# or clinic name" in a demo is embarrassing; a phone number reading
# "+91 00000 00001" is dangerous.
PLACEHOLDER_MARKERS = ("CHECK", "Add ", "Full Name", "example.com", "XXXX")

# Numbers that cannot be real. Caught before a patient dials one.
FAKE_NUMBER_PATTERNS = ("00000", "12345", "xxxxx", "99999")

MIN_PHONE_DIGITS = 8
MAX_PHONE_DIGITS = 15


# How many affected entries to name before summarising the rest. A directory
# where every entry shares a problem should say so in one line, not fifteen.
MAX_LISTED = 6


class Report:
    """Collected findings, grouped by severity and then by kind.

    Findings are stored as (kind, subject, detail) rather than finished
    sentences so that one problem affecting fifteen entries prints as one line
    with fifteen names, not fifteen near-identical lines. The first version of
    this printed 29 warnings for a 14-entry file, 28 of which were two messages
    repeated — which buried the one that actually mattered.
    """

    def __init__(self):
        self.errors: List[Tuple[str, str, str]] = []
        self.warnings: List[Tuple[str, str, str]] = []
        self.info: List[str] = []

    def error(self, kind: str, subject: str = "", detail: str = "") -> None:
        self.errors.append((kind, subject, detail))

    def warn(self, kind: str, subject: str = "", detail: str = "") -> None:
        self.warnings.append((kind, subject, detail))

    def note(self, message: str) -> None:
        self.info.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors

    @staticmethod
    def render(findings: List[Tuple[str, str, str]], marker: str) -> List[str]:
        grouped: Dict[str, List[Tuple[str, str]]] = {}
        for kind, subject, detail in findings:
            grouped.setdefault(kind, []).append((subject, detail))

        lines = []
        for kind, entries in grouped.items():
            named = [(s, d) for s, d in entries if s]
            if not named:
                lines.append(f"  {marker} {kind}")
                continue

            # One offender, or several with their own specifics: list them.
            if len(named) == 1 or any(d for _, d in named):
                lines.append(f"  {marker} {kind}")
                for subject, detail in named[:MAX_LISTED]:
                    lines.append(f"      {subject}{f' — {detail}' if detail else ''}")
                if len(named) > MAX_LISTED:
                    lines.append(f"      … and {len(named) - MAX_LISTED} more")
            else:
                # Same problem, no specifics: one line naming who.
                shown = ", ".join(s for s, _ in named[:MAX_LISTED])
                extra = f" … +{len(named) - MAX_LISTED} more" if len(named) > MAX_LISTED else ""
                lines.append(f"  {marker} {kind} ({len(named)})")
                lines.append(f"      {shown}{extra}")
        return lines


def _label(entry: Dict, index: int) -> str:
    """How to refer to an entry in a message the reader can act on."""
    return str(entry.get("id") or entry.get("name") or f"entry #{index}")


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _check_phone(report: Report, who: str, field: str, value) -> None:
    if not value:
        return

    text = str(value)
    digits = _digits(text)

    lowered = text.lower()
    if any(pattern in lowered for pattern in FAKE_NUMBER_PATTERNS):
        report.error("phone number is placeholder digits — it will not ring", who,
                     f"{field}={text}")
        return

    if digits and len(set(digits)) == 1:
        report.error("phone number is the same digit repeated", who, f"{field}={text}")
        return

    if len(digits) < MIN_PHONE_DIGITS:
        report.error("phone number is too short to dial", who,
                     f"{field}={text} ({len(digits)} digits)")
    elif len(digits) > MAX_PHONE_DIGITS:
        report.error("phone number is too long to dial", who,
                     f"{field}={text} ({len(digits)} digits)")


def _check_coordinates(report: Report, who: str, entry: Dict) -> bool:
    """Returns True if the entry has usable coordinates."""
    lat, lng = entry.get("lat"), entry.get("lng")

    if lat is None and lng is None:
        report.warn("no lat/lng — will not appear in distance sorting", who)
        return False

    if lat is None or lng is None:
        report.error("only one of lat/lng — both are needed, so both are ignored", who)
        return False

    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        report.error("lat/lng are not numbers", who,
                     f"({entry.get('lat')!r}, {entry.get('lng')!r})")
        return False

    # Swap detection runs before the range check on purpose. Copying
    # coordinates in the wrong order is the most common mistake here, and for an
    # Indian location it usually produces a latitude above 90 — so a plain
    # "out of range" would be technically true and useless. "You have them the
    # wrong way round, here are the right values" is what the reader can act on.
    in_india = INDIA_LAT[0] <= lat <= INDIA_LAT[1] and INDIA_LNG[0] <= lng <= INDIA_LNG[1]
    swapped_looks_right = (
        INDIA_LAT[0] <= lng <= INDIA_LAT[1] and INDIA_LNG[0] <= lat <= INDIA_LNG[1]
    )
    if swapped_looks_right and not in_india:
        report.error("lat/lng look swapped", who, f"({lat}, {lng}) — try lat={lng}, lng={lat}")
        return False

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        report.error("lat/lng out of range", who, f"({lat}, {lng})")
        return False

    if not in_india:
        report.warn("coordinates are outside India — intended?", who, f"({lat}, {lng})")

    return True


def _distance_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance. Matches the formula the frontend ranks with."""
    radius = 6371.0
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(h))


def _check_spread(report: Report, entries: List[Dict]) -> None:
    """Flag an entry that sits implausibly far from the rest of the directory.

    Every other coordinate check asks whether a point is valid on its own. This
    one asks whether it belongs with its neighbours, which is the only way to
    catch a well-formed coordinate for the wrong place -- the failure mode that
    actually happens when someone looks a hospital up and copies the first
    result.

    Compared against the median rather than the mean, so one bad entry cannot
    drag the centre towards itself and mask its own distance from everything.
    """
    located = [
        (e.get("name") or "?", float(e["lat"]), float(e["lng"]))
        for e in entries
        if isinstance(e, dict) and e.get("lat") is not None and e.get("lng") is not None
    ]
    if len(located) < 3:
        return  # too few to say what "with the others" means

    centre = (
        statistics.median(lat for _, lat, _ in located),
        statistics.median(lng for _, _, lng in located),
    )
    distances = {
        name: _distance_km(centre, (lat, lng)) for name, lat, lng in located
    }
    typical = statistics.median(distances.values())

    for name, distance in distances.items():
        if distance < OUTLIER_FLOOR_KM:
            continue
        if typical > 0 and distance < typical * OUTLIER_RATIO:
            continue
        # A warning, not an error. The coordinate may be perfectly correct for a
        # directory that legitimately covers a wide area, and this tool has no
        # way to tell that from a mistake -- but it is the one thing worth a
        # second pair of eyes, because nothing else here can catch it.
        report.warn(
            f"sits {distance:,.0f} km from the rest of the directory "
            f"(typical is {typical:,.0f} km) — check this is the right place",
            name,
            f"({[lat for n, lat, _ in located if n == name][0]}, "
            f"{[lng for n, _, lng in located if n == name][0]})",
        )


def _check_hours(report: Report, who: str, entry: Dict) -> bool:
    raw = entry.get("hours")
    if raw is None:
        report.warn("no hours — card will read 'Hours not listed'", who)
        return False

    parsed = hours_module.normalise(raw)
    if parsed is None:
        # The runtime silently degrades this to "unknown". Here it is an error,
        # because someone wrote hours believing they would be used.
        report.error("hours were provided but none could be parsed", who)
        return False

    if parsed.get("always_open"):
        return True

    # A day listed but dropped means one bad interval among good ones.
    for day in hours_module.DAYS:
        given = raw.get(day) if isinstance(raw, dict) else None
        if given and day not in parsed:
            report.error("some hours could not be parsed and were dropped", who,
                         f"{day}={given!r}")

    return True


def _check_placeholders(report: Report, who: str, entry: Dict) -> None:
    for field, value in entry.items():
        if not isinstance(value, str):
            continue
        for marker in PLACEHOLDER_MARKERS:
            if marker.lower() in value.lower():
                report.warn("still contains template text — fill in or delete the field",
                            who, f"{field}: {value[:44]}")
                break


def check(entries: List[Dict]) -> Report:
    report = Report()
    seen_ids: Dict[str, str] = {}
    covered: Dict[str, int] = {}
    with_coordinates = 0

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            report.error("entry is not an object", f"entry #{index}")
            continue

        who = _label(entry, index)

        # --- the two fields doctors.py silently drops an entry for ---------
        name = str(entry.get("name") or "").strip()
        if not name:
            report.error("no name — this entry will be skipped entirely", who)

        specialty = str(entry.get("specialty") or "").strip()
        if not specialty:
            report.error("no specialty — this entry will be skipped entirely", who)
        elif specialty not in SPECIALTIES:
            report.error(
                "unknown specialty — this entry will be skipped. Valid ids: "
                + ", ".join(sorted(SPECIALTIES)),
                who,
                repr(specialty),
            )
        else:
            covered[specialty] = covered.get(specialty, 0) + 1

        entry_id = str(entry.get("id") or "").strip()
        if entry_id:
            if entry_id in seen_ids:
                report.error("duplicate id", who, f"{entry_id!r} also on {seen_ids[entry_id]}")
            seen_ids[entry_id] = name or who

        # --- things a patient would act on --------------------------------
        for field in ("phone", "whatsapp", "assistant_phone"):
            _check_phone(report, who, field, entry.get(field))

        if not entry.get("phone"):
            report.warn("no phone number — the card will have no Call button", who)

        if entry.get("assistant_name") and not entry.get("assistant_phone"):
            report.warn("assistant named but no assistant_phone", who)

        if _check_coordinates(report, who, entry):
            with_coordinates += 1
        _check_hours(report, who, entry)
        _check_placeholders(report, who, entry)

        if not entry.get("languages"):
            report.warn("no languages listed", who)

    # --- directory-wide checks --------------------------------------------
    missing = sorted(set(SPECIALTIES) - set(covered))
    if missing:
        report.warn(
            "specialities with nobody listed — triage results for these dead-end: "
            + ", ".join(missing)
        )

    emergency = [
        e
        for e in entries
        if isinstance(e, dict) and e.get("specialty") == "emergency_medicine"
    ]
    if not emergency:
        report.error(
            "no emergency_medicine entry — every emergency result would lead nowhere"
        )
    elif not any(
        (hours_module.normalise(e.get("hours")) or {}).get("always_open")
        for e in emergency
    ):
        report.warn(
            "no emergency entry is marked always_open — an emergency at 3am would "
            "show only closed departments"
        )

    _check_spread(report, entries)

    report.note(f"{len(entries)} entries, {len(covered)} of {len(SPECIALTIES)} specialities covered")
    report.note(f"{with_coordinates} of {len(entries)} have coordinates for distance sorting")

    now = datetime.now()
    open_now = sum(
        1
        for e in entries
        if isinstance(e, dict)
        and hours_module.status(hours_module.normalise(e.get("hours")), now)["open"]
    )
    report.note(f"{open_now} open right now ({now.strftime('%a %H:%M')})")

    return report


def load(path: str) -> Tuple[List[Dict], Report]:
    report = Report()

    if not os.path.exists(path):
        report.error(f"{os.path.basename(path)} does not exist")
        return [], report

    try:
        # utf-8-sig matches doctors.py: Windows editors add a byte-order mark
        # that plain utf-8 rejects. Reading it the same way here means this
        # checker cannot pass a file the app would then fail to load.
        with open(path, encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        # By far the most common failure when hand-editing: a trailing comma or
        # a missing brace. The runtime falls back to placeholders without
        # complaint, so the file looks loaded when it is not.
        report.error(
            f"not valid JSON — line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )
        return [], report
    except OSError as exc:
        report.error(f"could not read the file: {exc}")
        return [], report

    if isinstance(raw, dict):
        raw = raw.get("doctors", [])
    if not isinstance(raw, list):
        report.error('file should hold a list of doctors, or {"doctors": [...]}')
        return [], report

    return raw, report


def main(argv: List[str]) -> int:
    path = argv[1] if len(argv) > 1 else DEFAULT_FILE
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(path):
        path = os.path.join(here, path)

    print(f"Checking {os.path.basename(path)}\n")

    entries, report = load(path)
    if entries:
        found = check(entries)
        report.errors += found.errors
        report.warnings += found.warnings
        report.info += found.info

    for line in report.info:
        print(f"  {line}")

    if report.warnings:
        print(f"\nWARNINGS ({len(report.warnings)}) — worth fixing:")
        for line in Report.render(report.warnings, "!"):
            print(line)

    if report.errors:
        print(f"\nERRORS ({len(report.errors)}) — fix before anyone uses this:")
        for line in Report.render(report.errors, "x"):
            print(line)

    print()
    if report.errors:
        print(f"FAILED — {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        return 1

    if report.warnings:
        print(f"OK with {len(report.warnings)} warning(s). Nothing will mislead a patient.")
    else:
        print("OK — no problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
