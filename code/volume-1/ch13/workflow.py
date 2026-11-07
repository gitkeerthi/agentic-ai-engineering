"""Chapter 13 demo: the investigation workflow run by hand, with either version of the interpreter's
instructions.

    uv run python ch13/workflow.py [SHIPMENT_ID] [--version A|B]

Prints the steps that ran, the finding, what the run cost and its outcome.
"""

import argparse
import asyncio
import time

from agentlab.usage import mark, since
from steps import Flagged, interpreter, investigation
from versions import VERSIONS

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("shipment_id", nargs="?", default="SH-4471")
parser.add_argument("--version", choices=VERSIONS, default="A")
args = parser.parse_args()

agent = interpreter(instructions=VERSIONS[args.version])


async def main() -> None:
    start, began = mark(), time.monotonic()
    result = await investigation(agent).run(args.shipment_id)
    seconds = time.monotonic() - began
    print(
        "Steps run:",
        " > ".join(e.executor_id for e in result if e.type == "executor_invoked"),
    )
    [output] = result.get_outputs()
    if isinstance(output, Flagged):
        print(f"\nFlagged ({output.reason}): {output.problems}")
        finding, outcome = output.finding, "flagged"
    else:
        finding, outcome = output, "finding"
    print(f"\nFinding:\n{finding.model_dump_json(indent=2) if finding else 'none'}")
    print(f"\nCost: {since(start)}; seconds: {seconds:.1f}")
    print(f"Outcome: {outcome}; {finding.status if finding else 'no finding'}")


asyncio.run(main())
