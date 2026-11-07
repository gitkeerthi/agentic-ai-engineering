"""Chapter 12 demo: the case set run against the real model, each case several times, scored from the typed
output.

    uv run python ch12/run_cases.py [REPEATS]

Prints every run's output in full, then one row per case: the known answer and how many runs matched it. A
case whose shipment never reaches the agent step makes no model call, so it runs once.
"""

import asyncio
import sys

from agentlab.usage import mark, since
from case_set import CASES, answer, misses
from steps import Flagged, interpreter, investigation

repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 5
agent = interpreter()


async def main() -> None:
    start, rows = mark(), []
    for case in CASES:
        matched = runs = 0
        for run in range(1, repeats + 1):
            calls = mark()
            [output] = (
                await investigation(agent).run(case["shipment_id"])
            ).get_outputs()
            runs += 1
            wrong = misses(case, output)
            matched += not wrong
            print(
                f"=== {case['shipment_id']} ({case['case']}), run {run}: "
                f"{answer(output)}"
            )
            if isinstance(output, Flagged):
                print(f"Flagged problems: {output.problems}")
                output = output.finding
            print(output.model_dump_json(indent=2) if output else "no finding")
            print("Misses:", wrong or "none")
            if mark() == calls:  # no model call: every run would be the same
                break
        rows.append((case, matched, runs))
    print("\n=== Scores")
    for case, matched, runs in rows:
        print(
            f"{case['shipment_id']}  {case['case']:<24} {matched} of {runs}  "
            f"{case['expected']}"
        )
    print(f"\nCost: {since(start)}")


asyncio.run(main())
