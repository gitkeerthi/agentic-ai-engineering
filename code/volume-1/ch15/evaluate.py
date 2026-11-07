"""Chapter 15: the application's investigation run on every case in the golden set, N times each, every
run saved in full with its seven-part configuration, usage and cost.

    uv run python ch15/evaluate.py STORE [--runs N]

Writes ch15/store/STORE/ (runs, spans, logs, metrics, evidence). A case that ends before the agent
step makes no model call, so it runs once. score.py reads the runs; it costs nothing to rerun.
"""

import argparse
import asyncio
import os
import shutil
from pathlib import Path

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("store")
parser.add_argument("--runs", type=int, default=10)
args = parser.parse_args()

STORE = Path(__file__).parent / "store" / args.store
shutil.rmtree(STORE, ignore_errors=True)
os.environ["COBALT_STATE"] = str(STORE / "state")  # the batch's own stand-in records

from agentlab.usage import mark, since  # noqa: E402
from cobalt_exceptions.agents import telemetry  # noqa: E402
from cobalt_exceptions.agents.interpreter import interpreter  # noqa: E402
from cobalt_exceptions.agents.steps import investigation  # noqa: E402
from cobalt_exceptions.domain.contracts import InvestigationRequest  # noqa: E402
from cobalt_exceptions.systems import records  # noqa: E402
from golden import CASES, answer, right  # noqa: E402

records.reset()
telemetry.setup(STORE)
agent = interpreter(middleware=[telemetry.keep_evidence])


async def main() -> None:
    start = mark()
    for case in CASES:
        for n in range(1, args.runs + 1):
            calls = mark()
            request = InvestigationRequest(
                shipment_id=case["shipment_id"], requested_by="evaluation"
            )
            run = await telemetry.investigate(investigation(agent), agent, request)
            typed = answer(run["output"])
            verdict = (
                "right" if right(case["shipment_id"], run["output"]) else "WRONG"
            )
            print(
                f"{case['shipment_id']} {n:>2} {verdict:<5} {typed.get('ending')} {typed.get('reason', '')} {typed.get('status', '')} trace {run['trace_id'][:8]}"
            )
            if mark() == calls:  # no model call: every run would be the same
                break
    print(f"Cost: {since(start)}")


asyncio.run(main())
telemetry.close()
