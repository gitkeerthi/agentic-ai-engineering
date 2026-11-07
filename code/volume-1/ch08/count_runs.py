"""Run one Chapter 8 program several times and print each run in full.

    uv run python ch08/count_runs.py 5 ch08/limit_report.py
    uv run python ch08/count_runs.py 5 ch08/limit_report.py --report
"""

import subprocess
import sys

runs, command = int(sys.argv[1]), sys.argv[2:]
for run in range(1, runs + 1):
    output = subprocess.run([sys.executable, *command], capture_output=True, text=True).stdout
    print(f"======== Run {run}\n{output}")
