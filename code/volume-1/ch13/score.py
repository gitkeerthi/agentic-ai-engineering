"""Chapter 13 demo, no model: score saved runs with the checks code can make, per version and split.

    uv run python ch13/score.py [VERSION ...]

Reads ch13/results/VERSION.jsonl (written by run_eval.py) for each version (default A B) and prints, for each
check in golden.py, how many of the runs it applies to passed it. A check that doesn't apply to a run (a case
that ends before the agent step, or a run with no accepted report) isn't counted. Where judge.py has judged a
version's runs (ch13/results/judged-VERSION-flash.jsonl), prints the judge's verdicts over the runs that reach
the agent, and its verdicts on every wrong Finding the workflow released.
"""

import json
import sys
from pathlib import Path

from golden import CASES, CHECKS, CRITERIA, SPLITS

versions = sys.argv[1:] or ["A", "B"]
by_id = {case["shipment_id"]: case for case in CASES}
runs = {
    version: [
        json.loads(line)
        for line in (Path(__file__).parent / "results" / f"{version}.jsonl")
        .read_text()
        .splitlines()
    ]
    for version in versions
}


def tally(check, saved: list[dict]) -> str:
    results = [check(by_id[run["shipment_id"]], run) for run in saved]
    counted = [r for r in results if r is not None]
    return f"{sum(counted)}/{len(counted)}" if counted else "-"


columns = [(v, split) for v in versions for split in SPLITS]
print(
    f"{'Dimension':<26} {'Check':<42}"
    + "".join(f"{v + ' ' + s[:4]:>11}" for v, s in columns)
)
for dimension, name, check in CHECKS:
    cells = [
        tally(check, [r for r in runs[v] if r["split"] == split])
        for v, split in columns
    ]
    print(f"{dimension:<26} {name:<42}" + "".join(f"{c:>11}" for c in cells))

judged = {
    v: {
        (r["shipment_id"], r["run"]): r["verdict"]
        for r in map(json.loads, path.read_text().splitlines())
    }
    for v in versions
    if (
        path := Path(__file__).parent / "results" / f"judged-{v}-flash.jsonl"
    ).exists()
}
if judged:
    print(
        "\nThe judge's verdicts (flash); a run with no accepted report counts as a fail:"
    )
    for criterion in [*CRITERIA, "all four", "typed answer and all four"]:
        cells = []
        for v, split in columns:
            agent_runs = [r for r in runs[v] if r["split"] == split and r["query"]]
            verdicts = [
                judged[v].get((r["shipment_id"], r["run"])) for r in agent_runs
            ]
            passed = sum(
                bool(verdict) and all(verdict.values()) and not run["misses"]
                if criterion == "typed answer and all four"
                else bool(verdict) and all(verdict.values())
                if criterion == "all four"
                else bool(verdict and verdict[criterion])
                for run, verdict in zip(agent_runs, verdicts)
            )
            cells.append(f"{passed}/{len(agent_runs)}")
        print(f"{'Judged':<26} {criterion:<42}" + "".join(f"{c:>11}" for c in cells))
    print("\nThe judge's verdicts on the wrong Findings the workflow released:")
    for v in versions:
        for r in runs[v]:
            if r["answer"]["ending"] == "finding" and r["misses"]:
                verdict = judged[v][(r["shipment_id"], r["run"])]
                marks = " ".join(
                    f"{c}={'yes' if verdict[c] else 'no'}" for c in CRITERIA
                )
                print(f"  {v} {r['shipment_id']} run {r['run']}: {marks}")

print("\nRuns per case, matching the known answer (the workflow's typed output):")
for case in CASES:
    cells = []
    for v in versions:
        saved = [r for r in runs[v] if r["shipment_id"] == case["shipment_id"]]
        cells.append(f"{v} {sum(not r['misses'] for r in saved)}/{len(saved)}")
    print(
        f"  {case['shipment_id']}  {case['split']:<12} {case['case']:<36} {'  '.join(cells)}"
    )
