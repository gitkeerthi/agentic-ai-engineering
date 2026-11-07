"""Run one Chapter 9 program several times and count the outcomes it reports.

    uv run python ch09/count_runs.py 10 ch09/typed_note.py
    uv run python ch09/count_runs.py 10 ch09/typed_note.py --no-note
"""

import subprocess
import sys
from collections import Counter

runs, command = int(sys.argv[1]), sys.argv[2:]
outcomes = Counter()
for run in range(1, runs + 1):
    output = subprocess.run([sys.executable, *command], capture_output=True, text=True).stdout
    outcome = next((line[9:] for line in output.splitlines() if line.startswith("Outcome: ")), "no outcome printed")
    outcomes[outcome] += 1
    print(f"======== Run {run}: {outcome}\n{output}")
print("======== Totals")
for outcome, count in outcomes.most_common():
    print(f"{count} of {runs}: {outcome}")
