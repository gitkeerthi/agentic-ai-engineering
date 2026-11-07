"""Chapter 12 demo: Chapter 11's investigation workflow, run by hand, with or without the change in
the_change.py.

    uv run python ch12/workflow.py [SHIPMENT_ID] [--store-busy] [--with-change]

--store-busy makes the document store answer every search with "busy". --with-change builds the workflow
with the changed document check, which carries on past a busy store.
"""

import argparse
import asyncio
import time

from agent_framework.exceptions import ChatClientException

from agentlab.usage import mark, since
from cobalt import make_store_busy
from steps import Flagged, StoreUnavailable, interpreter, investigation
from the_change import investigation_with_change

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("shipment_id", nargs="?", default="SH-4471")
parser.add_argument("--store-busy", action="store_true")
parser.add_argument("--with-change", action="store_true")
args = parser.parse_args()
if args.store_busy:
    make_store_busy()
build = investigation_with_change if args.with_change else investigation


agent = interpreter()  # one agent, shared by every workflow this program builds


async def main() -> None:
    start, began = mark(), time.monotonic()
    try:
        result = await build(agent).run(args.shipment_id)  # ①
    except (StoreUnavailable, ChatClientException) as error:  # ②
        failure = type(error).__name__
        print(f"The workflow stopped: {failure}: {error}")
        print(f"\nCost: {since(start)}; seconds: {time.monotonic() - began:.1f}")
        print(f"Outcome: stopped; {failure}")
        return
    seconds = time.monotonic() - began
    print(
        "Steps run:",
        " > ".join(e.executor_id for e in result if e.type == "executor_invoked"),
    )
    [output] = result.get_outputs()  # ③
    if isinstance(output, Flagged):
        print(f"\nFlagged ({output.reason}): {output.problems}")
        finding, outcome = output.finding, "flagged"
    else:
        finding, outcome = output, "finding"
    print(f"\nFinding:\n{finding.model_dump_json(indent=2) if finding else 'none'}")
    print(f"\nCost: {since(start)}; seconds: {seconds:.1f}")
    print(f"Outcome: {outcome}; {finding.status if finding else 'no finding'}")


asyncio.run(main())
