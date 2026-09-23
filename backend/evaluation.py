"""Measure how accurate the triage actually is.

    python evaluation.py                     # development set + sealed held-out summary
    python evaluation.py --brief             # one line each, for a pre-deploy check
    python evaluation.py --holdout --reveal  # show held-out failures (spends them)

Two sets, and why
-----------------
eval_cases.py is the development set: its failures get read and fixed, so its
score shows how well the app fits cases it was fitted to. eval_holdout.py is
never tuned against, so its score is the honest one. Read the docstring there
before touching it.

What counts as dangerous
------------------------
A single accuracy figure is the wrong measure for triage, because the ways of
being wrong are not comparable. The headline is the count of dangerous misses:

  - an emergency or urgent case graded lower than it should be;
  - a crisis disclosure that did not reach the counselling path;
  - an emergency or urgent case sent to the crisis path instead of to care.

A minor complaint the app did not understand is reported, but it is not
dangerous. An "unknown" result asks the person to describe it again; for a cold
that is a nuisance, for a stroke it is a delay. The first version of this file
counted both as under-triage and overstated the danger by three cases.

Over-triage is the documented design ("when in doubt, escalate") and is bounded
rather than eliminated: an app that answered "emergency" to everything would
have no dangerous misses and be useless.

What a pass does not mean
-------------------------
The labels come from the same non-clinician source as the rules, so agreement is
consistency rather than correctness. A score here is a floor to defend, not
evidence the app is safe.
"""

import hashlib
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from typing import Dict, List

import main
from eval_cases import CASES, LEVEL_ORDER, Case
from eval_holdout import BASELINE, FINGERPRINT, HOLDOUT

URGENT = {"urgent_care", "emergency"}


def _rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 0


def grade(case: Case) -> str:
    """Run one case through the real endpoint."""
    payload = {"message": case.text, "lang": case.lang}
    if case.age is not None:
        payload["age"] = case.age
    if case.duration is not None:
        payload["duration"] = case.duration
    return main.triage(main.TriageRequest(**payload))["urgency_level"]


def classify(expected: str, got: str) -> str:
    """exact | under | missed_crisis | wrong_pathway | not_understood | over"""
    if expected == got:
        return "exact"
    if expected == "crisis":
        return "missed_crisis"
    if got == "crisis":
        return "wrong_pathway"
    if _rank(got) > _rank(expected):
        return "over"
    if expected in URGENT:
        return "under"
    return "not_understood"


def is_dangerous(expected: str, got: str) -> bool:
    """The failures that can hurt someone. See the module docstring."""
    outcome = classify(expected, got)
    if outcome in ("under", "missed_crisis"):
        return True
    # Sent to a counsellor when they needed a doctor.
    return outcome == "wrong_pathway" and expected in URGENT


def evaluate(cases: List[Case]) -> Dict:
    results = []
    for case in cases:
        got = grade(case)
        results.append((case, got, classify(case.expected, got), is_dangerous(case.expected, got)))

    scored = [r for r in results if not r[0].expected_miss]
    known = [r for r in results if r[0].expected_miss]
    outcomes = Counter(outcome for _, _, outcome, _ in scored)
    dangerous = [r for r in scored if r[3]]
    total = len(scored) or 1

    by_category = defaultdict(lambda: {"total": 0, "exact": 0, "dangerous": 0})
    by_language = defaultdict(lambda: {"total": 0, "exact": 0, "dangerous": 0})
    for case, _, outcome, danger in scored:
        for table, key in ((by_category, case.category or "uncategorised"), (by_language, case.lang)):
            table[key]["total"] += 1
            table[key]["exact"] += outcome == "exact"
            table[key]["dangerous"] += danger

    return {
        "results": results,
        "scored": scored,
        "known_gaps": known,
        "total": len(scored),
        "exact": outcomes["exact"],
        "accuracy": outcomes["exact"] / total,
        "dangerous": len(dangerous),
        "dangerous_rate": len(dangerous) / total,
        "under": outcomes["under"],
        "missed_crisis": outcomes["missed_crisis"],
        "wrong_pathway": outcomes["wrong_pathway"],
        "not_understood": outcomes["not_understood"],
        "over": outcomes["over"],
        "over_rate": outcomes["over"] / total,
        "by_category": dict(by_category),
        "by_language": dict(by_language),
    }


def fingerprint(cases: List[Case]) -> str:
    """A hash of the cases' content, stable across runs and machines."""
    canonical = json.dumps(
        sorted(
            [c.id, c.text, c.expected, c.lang, c.age, c.duration, c.category, c.expected_miss]
            for c in cases
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------- reporting

def _bar(value: float, width: int = 26) -> str:
    filled = round(value * width)
    return "#" * filled + "." * (width - filled)


def _summary_lines(verdict: Dict) -> List[str]:
    lines = [
        f"  cases scored        {verdict['total']}",
        f"  exact match         {verdict['exact']:>3}  {verdict['accuracy']:6.1%}  {_bar(verdict['accuracy'])}",
        f"  DANGEROUS MISSES    {verdict['dangerous']:>3}  {verdict['dangerous_rate']:6.1%}",
    ]
    if verdict["dangerous"]:
        parts = [
            (verdict["under"], "graded too low"),
            (verdict["missed_crisis"], "crisis missed"),
            (sum(1 for c, _, o, d in verdict["scored"] if o == "wrong_pathway" and d), "sent to crisis instead of care"),
        ]
        lines.append("                      " + ", ".join(f"{n} {label}" for n, label in parts if n))
    lines += [
        f"  over-triaged        {verdict['over']:>3}  {verdict['over_rate']:6.1%}  (cautious, bounded)",
        f"  not understood      {verdict['not_understood']:>3}         (minor complaint, asked to rephrase)",
    ]
    return lines


def report_development(verdict: Dict) -> None:
    print("=" * 74)
    print("DEVELOPMENT SET — eval_cases.py (tuned against; optimistic by design)")
    print("=" * 74)
    print("\n".join(_summary_lines(verdict)))

    failures = [r for r in verdict["scored"] if r[2] != "exact"]
    if failures:
        print("\n  disagreements")
        order = ("under", "missed_crisis", "wrong_pathway", "not_understood", "over")
        for case, got, outcome, danger in sorted(failures, key=lambda r: order.index(r[2])):
            flag = "!!" if danger else "  "
            print(f"  {flag} [{case.id}] {outcome}: expected {case.expected}, got {got}")
            print(f"        {case.text[:66]}")

    if verdict["known_gaps"]:
        print("\n  known gaps (recorded, not scored)")
        for case, got, outcome, _ in verdict["known_gaps"]:
            mark = "NOW PASSES" if outcome == "exact" else f"got {got}"
            print(f"     [{case.id}] expected {case.expected}, {mark}")


def report_holdout_sealed(verdict: Dict) -> None:
    """Aggregates only. Never prints a case."""
    print("\n" + "=" * 74)
    print("HELD-OUT SET — eval_holdout.py (never tuned against; the honest number)")
    print("=" * 74)
    print("\n".join(_summary_lines(verdict)))

    if BASELINE:
        delta_exact = verdict["exact"] - BASELINE["exact"]
        delta_danger = verdict["dangerous"] - BASELINE["dangerous"]
        print(
            f"\n  vs first blind run ({BASELINE['recorded']}): "
            f"exact {BASELINE['exact']} -> {verdict['exact']} ({delta_exact:+d}), "
            f"dangerous {BASELINE['dangerous']} -> {verdict['dangerous']} ({delta_danger:+d})"
        )

    print("\n  by clinical area            exact     dangerous")
    for category, row in sorted(verdict["by_category"].items()):
        print(f"    {category:<24} {row['exact']:>2}/{row['total']:<2}      {row['dangerous']:>2}")

    print("\n  by language                 exact     dangerous")
    for lang, row in sorted(verdict["by_language"].items()):
        print(f"    {lang:<24} {row['exact']:>2}/{row['total']:<2}      {row['dangerous']:>2}")

    print("\n  Sealed. Weak areas are the cue to write NEW development cases there.")
    print("  --holdout --reveal shows the cases, and spends them. See eval_holdout.py.")


def report_holdout_revealed(verdict: Dict) -> None:
    print("\n" + "!" * 74)
    print("REVEALING HELD-OUT CASES. Every case printed below is now spent.")
    print("Move each into eval_cases.py before fixing it, write a fresh replacement")
    print("here, then update FINGERPRINT and re-record BASELINE.")
    print("!" * 74)
    for case, got, outcome, danger in verdict["scored"]:
        if outcome == "exact":
            continue
        flag = "!!" if danger else "  "
        print(f"  {flag} [{case.id}] {outcome}: expected {case.expected}, got {got}")
        print(f"        {case.text}")


def main_cli(argv: List[str]) -> int:
    development = evaluate(CASES)
    holdout = evaluate(HOLDOUT)

    if "--brief" in argv:
        for name, v in (("development", development), ("held-out", holdout)):
            print(
                f"{name:<12} {v['accuracy']:4.0%} exact ({v['exact']}/{v['total']}), "
                f"{v['dangerous']} dangerous, {v['over']} over-triaged"
            )
    elif "--holdout" in argv and "--reveal" in argv:
        report_holdout_sealed(holdout)
        report_holdout_revealed(holdout)
    else:
        report_development(development)
        report_holdout_sealed(holdout)

    # Blocks on a dangerous miss in development, or on the held-out set getting
    # worse than its first blind run. A held-out miss present from the start does
    # not block: blocking on it would be pressure to tune against it.
    regressed = BASELINE is not None and holdout["dangerous"] > BASELINE["dangerous"]
    return 1 if development["dangerous"] or regressed else 0


if __name__ == "__main__":
    # Offline extraction, so a score never depends on a third-party API being up
    # or on which model happened to answer.
    main.extract_symptoms_llm = lambda text: None

    # Every case goes through the real /triage endpoint, which writes an audit
    # record exactly as a real request would. Pointed at a throwaway database so
    # an evaluation run cannot file a hundred invented complaints into the real
    # audit trail — which the first version of this script did, 176 rows of it,
    # into the table /audit/unrecognised reads to decide what the vocabulary is
    # missing. conftest.py already does this for pytest; this is the same fix
    # for the command line.
    import audit

    audit.DB_FILE = os.path.join(tempfile.mkdtemp(prefix="triage-eval-"), "audit.db")
    audit._initialised = False

    sys.exit(main_cli(sys.argv))
