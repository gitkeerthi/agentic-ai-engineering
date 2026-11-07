"""Run one Chapter 5 program several times, print each run in full, then a line per run: the tools called and the Cause line.

    uv run python ch05/count_runs.py 5 ch05/hidden_outage.py
    uv run python ch05/count_runs.py 5 ch05/changed_response.py checked
"""

import re
import subprocess
import sys
from collections import Counter

runs, command = int(sys.argv[1]), sys.argv[2:]
summary = []
for run in range(1, runs + 1):
    output = subprocess.run([sys.executable, *command], capture_output=True, text=True).stdout
    print(f"======== Run {run}\n{output}")
    calls = Counter(re.findall(r"^Model asks: (\w+)\(", output, re.MULTILINE))
    cause = next((line.strip() for line in output.splitlines() if re.match(r"\W*Cause", line)), "(no Cause line)")
    summary.append(f"Run {run}: {dict(calls)}\n    {cause}")

print(f"======== Summary: {' '.join(command)}")
print("\n".join(summary))
