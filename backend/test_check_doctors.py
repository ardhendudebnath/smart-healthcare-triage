"""Validator tests. Run: python -m pytest test_check_doctors.py

Focused on the coordinate outlier check, because it is the only check in
check_doctors.py that cannot be reasoned about from a single entry, and the one
that exists because of a mistake that actually happened.
"""

import check_doctors
from check_doctors import OUTLIER_FLOOR_KM, OUTLIER_RATIO, Report, _check_spread

# The four Agartala campuses, as shipped.
AGARTALA = [
    {"name": "IGM", "lat": 23.8308, "lng": 91.2760},
    {"name": "AGMC", "lat": 23.8603, "lng": 91.2928},
    {"name": "TMC", "lat": 23.7847, "lng": 91.2592},
    {"name": "ILS", "lat": 23.8675, "lng": 91.2896},
]


def _flags(entries):
    report = Report()
    _check_spread(report, entries)
    return report.warnings


def test_the_real_directory_is_not_flagged():
    assert _flags(AGARTALA) == []


def test_the_coordinate_a_lookup_actually_returned_is_flagged():
    """The case this check was written for.

    Searching for IGM Hospital returned 23.49, 91.16 — inside India, the right
    way round, and about 39 km from Agartala, out past the Bangladesh border. It
    passes every other check in the file. Only its distance from its neighbours
    gives it away.
    """
    entries = [dict(e) for e in AGARTALA]
    entries[0] = {"name": "IGM", "lat": 23.49, "lng": 91.16}

    flagged = _flags(entries)
    assert len(flagged) == 1, flagged
    assert "IGM" in " ".join(str(part) for part in flagged[0])


def test_a_city_directory_is_not_flagged():
    """Entries ten kilometres apart are a normal city, not a mistake."""
    assert _flags([
        {"name": "a", "lat": 23.83, "lng": 91.28},
        {"name": "b", "lat": 23.90, "lng": 91.35},
        {"name": "c", "lat": 23.75, "lng": 91.20},
    ]) == []


def test_a_state_wide_directory_is_not_flagged():
    """The check must adapt to the scale of the directory it is given.

    A flat kilometre threshold cannot: the first attempt used 150 km, which is
    absurd for one city and still missed the 39 km error above. Measuring each
    entry against how spread out its own neighbours are handles both.
    """
    assert _flags([
        {"name": "a", "lat": 23.83, "lng": 91.28},
        {"name": "b", "lat": 24.32, "lng": 92.00},
        {"name": "c", "lat": 23.30, "lng": 91.50},
        {"name": "d", "lat": 24.00, "lng": 91.60},
    ]) == []


def test_entries_without_coordinates_are_ignored():
    """A missing coordinate is a gap in the directory, not a suspicious one."""
    entries = [dict(e) for e in AGARTALA]
    entries.append({"name": "no location", "lat": None, "lng": None})
    assert _flags(entries) == []


def test_too_few_located_entries_to_judge():
    """With two points there is no "rest of the directory" to be far from."""
    assert _flags(AGARTALA[:2]) == []


def test_a_tight_cluster_does_not_flag_a_slightly_further_entry():
    """The floor exists so a hospital two streets out is not called an error.

    Without it, a directory whose entries sit 200 m apart would flag anything
    more than 600 m away — every real directory would be full of warnings, and
    warnings nobody can act on are the fastest way to make people stop reading
    them.
    """
    flagged = _flags([
        {"name": "a", "lat": 23.8300, "lng": 91.2800},
        {"name": "b", "lat": 23.8310, "lng": 91.2810},
        {"name": "c", "lat": 23.8320, "lng": 91.2820},
        {"name": "d", "lat": 23.8500, "lng": 91.3000},  # ~3 km out
    ])
    assert flagged == []


def test_thresholds_are_sane():
    assert OUTLIER_RATIO > 1
    assert OUTLIER_FLOOR_KM > 0


def test_distance_matches_a_known_separation():
    """Sanity-check the haversine against a distance that can be verified.

    IGM to TMC Hapania is about 6 km apart on the ground; a formula error would
    show up here as a wildly different number rather than a subtly wrong one.
    """
    km = check_doctors._distance_km((23.8308, 91.2760), (23.7847, 91.2592))
    assert 4.0 < km < 8.0, km
