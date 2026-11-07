"""Run one Chapter 12 program several times, count the outcomes it reports, and average what the runs cost.

uv run python ch12/count_runs.py 5 ch12/workflow.py --store-busy --with-change
"""

import re
import subprocess
import sys
from collections import Counter

runs, command = int(sys.argv[1]), sys.argv[2:]
outcomes = Counter()
costs = []
for run in range(1, runs + 1):
    output = subprocess.run(
        [sys.executable, *command], capture_output=True, text=True
    ).stdout
    outcome = next(
        (line[9:] for line in output.splitlines() if line.startswith("Outcome: ")),
        "no outcome printed",
    )
    outcomes[outcome] += 1
    cost = next(
        (line for line in output.splitlines() if line.startswith("Cost: ")), ""
    )
    numbers = [
        float(n.replace(",", "")) for n in re.findall(r"[\d,]+(?:\.\d+)?", cost)
    ]
    if len(numbers) == 5:
        costs.append(
            numbers
        )  # model calls, input tokens, cached, output tokens, seconds
    print(f"======== Run {run}: {outcome}\n{output}")
print("======== Totals")
for outcome, count in outcomes.most_common():
    print(f"{count} of {runs}: {outcome}")
if costs:
    calls, tokens, cached, written, seconds = (
        sum(column) / len(costs) for column in zip(*costs)
    )
    print(
        f"Average per run: {calls:.1f} model calls; {tokens:,.0f} input tokens ({cached:,.0f} cached); "
        f"{written:,.0f} output tokens; {seconds:.1f} seconds"
    )
