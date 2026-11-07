"""Run one Chapter 7 program several times, print each run in full, then a line per run for its last question:
the tools it called and the first line of its answer.

    uv run python ch07/count_runs.py 5 ch07/stale_update.py
    uv run python ch07/count_runs.py 5 ch07/stale_update.py --still-held
"""

import re
import subprocess
import sys

runs, command = int(sys.argv[1]), sys.argv[2:]
summary = []
for run in range(1, runs + 1):
    output = subprocess.run([sys.executable, *command], capture_output=True, text=True).stdout
    print(f"======== Run {run}\n{output}")
    last = re.split(r"^(?:Run \d+|Question): ", output, flags=re.MULTILINE)[-1]
    tools = re.findall(r"^Model asks: (\w+\(.*?\))$", last, re.MULTILINE)
    answer = next((line.strip() for line in last.splitlines()[1:] if line.strip() and not line.startswith(("Model asks", "Sent:", "Stored"))), "(no answer)")
    summary.append(f"Run {run}: {len(tools)} tool calls {tools}\n    {answer[:200]}")

print(f"======== Summary: {' '.join(command)}")
print("\n".join(summary))
