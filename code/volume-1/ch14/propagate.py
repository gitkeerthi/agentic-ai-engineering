"""Chapter 14 demo, no model: one trace across two processes. A flagged case goes onto a review queue with its
trace context; reviewer.py, a separate process, takes it off and records its work in the same trace.

    uv run python ch14/propagate.py

The agent replies from a script (nothing_wrong for a held shipment, which the workflow flags), so the run costs
nothing. Prints the queued message's headers and the joined trace, read back from the
trace store.
"""

import asyncio
import json
import shutil
import subprocess
import sys

from opentelemetry.propagate import inject
from opentelemetry.trace import SpanKind

import telemetry
from agent_framework.observability import get_tracer
from scripted import ScriptedClient
from show import print_trace
from steps import interpreter, investigation

tracer = get_tracer(telemetry.SCOPE)

shutil.rmtree(telemetry.HERE / "store" / "propagate", ignore_errors=True)
store = telemetry.setup("propagate")
queue = store / "review-queue.jsonl"

NOTHING_WRONG = {
    "shipment_id": "SH-4588",
    "status": "nothing_wrong",
    "cause": None,
    "evidence": [
        {
            "record_id": "RTM-88377",
            "fact": "On hold: required document not received.",
        }
    ],
    "recommended_action": None,
    "refiling": None,
}
agent = interpreter(
    client=ScriptedClient([("report_finding", NOTHING_WRONG, "call_1")])
)


async def main() -> str:
    with tracer.start_as_current_span("handle investigation request"):
        record = await telemetry.investigate(investigation(agent), agent, "SH-4588")
        with tracer.start_as_current_span(
            "enqueue for review", kind=SpanKind.PRODUCER
        ):
            message = {
                "shipment_id": "SH-4588",
                "reason": record["output"]["reason"],
                "headers": {},
            }
            inject(message["headers"])  # ①
            queue.write_text(json.dumps(message) + "\n")
    return record["trace_id"]


trace_id = asyncio.run(main())
telemetry.close()
queued = json.loads(queue.read_text())
print(f"Queued {queued['shipment_id']} ({queued['reason']}) with headers:", flush=True)
print(f"  {queued['headers']}", flush=True)
subprocess.run([sys.executable, telemetry.HERE / "reviewer.py", queue], check=True)
print()
print_trace(store, trace_id)
