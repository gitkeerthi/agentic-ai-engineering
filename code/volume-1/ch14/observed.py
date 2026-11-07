"""Chapter 14 demo: one investigation, observed. The workflow runs inside a root span that carries the run's
configuration, usage, cost and outcome; every span goes to the trace store; the case system gets the outcome
with the trace ID; the evidence store gets what the agent was sent and replied.

    uv run python ch14/observed.py [SHIPMENT_ID] [--version A|B] [--store NAME]

Prints the case record and the run's trace, read back from the trace store.
"""

import argparse
import asyncio

import telemetry
from show import case_line, print_trace
from steps import interpreter, investigation
from versions import VERSIONS

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("shipment_id", nargs="?", default="SH-4471")
parser.add_argument("--version", choices=("A", "B"), default="A")
parser.add_argument("--store", default="observed")
args = parser.parse_args()

store = telemetry.setup(args.store)
agent = interpreter(
    instructions=VERSIONS[args.version], middleware=[telemetry.keep_evidence]
)


record = asyncio.run(
    telemetry.investigate(investigation(agent), agent, args.shipment_id)
)
telemetry.close()
print(case_line(record))
print()
print_trace(store, record["trace_id"])
