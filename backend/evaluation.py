"""Measure how accurate the triage actually is.

    python evaluation.py            # full report
    python evaluation.py --brief    # one line, for a pre-deploy check

Why under-triage and over-triage are counted separately
-------------------------------------------------------
A single accuracy percentage is the wrong measure for triage, because the two
ways of being wrong are not comparable. Telling someone with a stroke to rest at
home can kill them. Telling someone with a cold to attend the same day wastes an
afternoon. A system at 90% accuracy that fails downward is far worse than one at
80% that fails upward, and one number cannot tell them apart.

knowledge_graph.py already states the rule -- "when in doubt, escalate" -- so
this measures whether the code keeps the promise its own documentation makes.

The headline number is the under-triage rate. Everything else is context.

What a pass does not mean
-------------------------
The labels come from the same non-clinician source as the rules, so agreement
between them is consistency rather than correctness. See eval_cases.py. A score
here is a floor to defend during refactoring, not evidence the app is safe.
"""

import sys
from collections import Counter
from typing import Dict, List

import main
from eval_cases import CASES, LEVEL_ORDER, Case

# Crisis sits outside the urgency ladder: it is a different pathway, not a
# higher grade, so it is scored as an exact match or a miss and never as a
# direction of error.
OFF_LADDER = {"crisis"}


def _rank(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 0


def grade(case: Case) -> str:
    """Run one case through the real endpoint, offline extraction only."""
    payload = {"message": case.text, "lang": case.lang}
    if case.age is not None:
        payload["age"] = case.age
    if case.duration is not None:
        payload["duration"] = case.duration
    return main.triage(main.TriageRequest(**payload))["urgency_level"]


def classify(expected: str, got: str) -> str:
    """exact | under | over | wrong_pathway"""
    if expected == got:
        return "exact"
    if expected in OFF_LADDER or got in OFF_LADDER:
        return "wrong_pathway"
    return "under" if _rank(got) < _rank(expected) else "over"


def evaluate(cases: List[Case] = None) -> Dict:
    cases = cases if cases is not None else CASES
    results = []
    for case in cases:
        got = grade(case)
        results.append((case, got, classify(case.expected, got)))

    known = [r for r in results if r[0].expected_miss]
    live = [r for r in results if not r[0].expected_miss]

    outcomes = Counter(outcome for _, _, outcome in live)
    total = len(live) or 1

    return {
        "results": results,
        "live": live,
        "known_gaps": known,
        "total": len(live),
        "exact": outcomes["exact"],
        "under": outcomes["under"],
        "over": outcomes["over"],
        "wrong_pathway": outcomes["wrong_pathway"],
        "accuracy": outcomes["exact"] / total,
        # The number that matters. Anything above zero is a case where the app
        # told someone their problem was less urgent than it is.
        "under_triage_rate": outcomes["under"] / total,
        "over_triage_rate": outcomes["over"] / total,
    }


def _bar(value: float, width: int = 28) -> str:
    filled = round(value * width)
    return "#" * filled + "." * (width - filled)


def report(verdict: Dict) -> None:
    print("=" * 72)
    print("TRIAGE ACCURACY")
    print("=" * 72)
    print(f"  cases scored        {verdict['total']}")
    print(f"  exact match         {verdict['exact']:>3}  {verdict['accuracy']:6.1%}  {_bar(verdict['accuracy'])}")
    print(f"  over-triaged        {verdict['over']:>3}  {verdict['over_triage_rate']:6.1%}  (cautious, acceptable)")
    print(f"  UNDER-TRIAGED       {verdict['under']:>3}  {verdict['under_triage_rate']:6.1%}  (dangerous)")
    if verdict["wrong_pathway"]:
        print(f"  wrong pathway       {verdict['wrong_pathway']:>3}         (crisis confused with urgency)")

    failures = [(c, g, o) for c, g, o in verdict["live"] if o != "exact"]
    if failures:
        print("\n" + "-" * 72)
        print("DISAGREEMENTS")
        print("-" * 72)
        for outcome in ("under", "wrong_pathway", "over"):
            group = [f for f in failures if f[2] == outcome]
            if not group:
                continue
            print(f"\n  {outcome.replace('_', ' ').upper()}")
            for case, got, _ in group:
                print(f"    [{case.id}] expected {case.expected}, got {got}")
                print(f"        {case.text[:66]}")
                print(f"        {case.why}")

    if verdict["known_gaps"]:
        print("\n" + "-" * 72)
        print("KNOWN GAPS (recorded, not scored)")
        print("-" * 72)
        for case, got, outcome in verdict["known_gaps"]:
            mark = "now passes" if outcome == "exact" else f"got {got}"
            print(f"    [{case.id}] expected {case.expected}, {mark}")
            print(f"        {case.why}")

    print("\n" + "=" * 72)
    if verdict["under"] == 0:
        print("No under-triage on the scored set.")
    else:
        print(f"{verdict['under']} case(s) graded BELOW the expected urgency. Investigate before deploying.")
    print("Labels are not clinician-reviewed. See eval_cases.py.")
    print("=" * 72)


def main_cli(argv: List[str]) -> int:
    verdict = evaluate()
    if "--brief" in argv:
        print(
            f"triage accuracy {verdict['accuracy']:.0%} "
            f"({verdict['exact']}/{verdict['total']}), "
            f"under-triage {verdict['under']}, over-triage {verdict['over']}"
        )
    else:
        report(verdict)
    # Under-triage is the only failure that blocks. Over-triage is the design
    # working as documented.
    return 1 if verdict["under"] else 0


if __name__ == "__main__":
    # The offline extractor, so a score never depends on a third-party API being
    # up or on which model answered.
    main.extract_symptoms_llm = lambda text: None
    sys.exit(main_cli(sys.argv))
