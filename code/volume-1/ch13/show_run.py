"""Chapter 13 demo, no model: print one saved run of the evaluation.

    uv run python ch13/show_run.py VERSION SHIPMENT_ID RUN

Reads ch13/results/VERSION.jsonl (written by run_eval.py) and prints the run's configuration, the workflow's
typed answer and its misses, every report_finding call the agent made and whether it was accepted, any text
the agent wrote, and the finding it reported. Text the model wrote outside a tool call is cut to 300
characters.
"""

import json
import sys
from pathlib import Path

from agent_framework import AgentResponse

from golden import reports

version, shipment_id, number = sys.argv[1], sys.argv[2], int(sys.argv[3])
lines = (
    (Path(__file__).parent / "results" / f"{version}.jsonl").read_text().splitlines()
)
run = next(
    r
    for r in map(json.loads, lines)
    if r["shipment_id"] == shipment_id and r["run"] == number
)

print(
    f"Configuration: version {run['version']}, instructions {run['instructions_md5'][:8]}, "
    f"model {run['model']}, framework {run['framework']}, golden set {run['golden_set']}"
)
print(
    f"Case: {run['shipment_id']} ({run['case']}, {run['split']}), run {run['run']}"
)
print(f"Workflow's answer: {run['answer']}")
print(f"Misses: {run['misses'] or 'none'}")
if run["response"] is None:
    print("The workflow ended before the agent step.")
    sys.exit()
text = [
    m.text
    for m in AgentResponse.from_dict(run["response"]).messages
    if m.role == "assistant" and m.text
]
for words in text:
    print(f"Text the agent wrote: {words[:300]}")
calls = reports(run)
print(f"report_finding calls: {len(calls)}; accepted: {[ok for _, ok in calls]}")
accepted = [arguments for arguments, ok in calls if ok]
if accepted:
    print("Reported finding:")
    print(json.dumps(json.loads(accepted[-1]), indent=2))
