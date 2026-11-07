"""Chapter 5 demo: the document store is slow to answer. Which time limits stop the wait?"""

import argparse
import asyncio
import logging
import time
from typing import Annotated

from agent_framework import tool

from cobalt import SLOW_SECONDS, get_customs_case, get_shipment_status, list_required_documents, store
from investigate import TASK, investigator, show

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--duration-limit", type=float, help="the framework's max_duration_seconds (default: none)")
parser.add_argument("--tool-timeout", type=float, help="seconds the tool waits for the store (default: no limit)")
parser.add_argument("--run-timeout", type=float, help="seconds the program waits for the whole run (default: no limit)")
args = parser.parse_args()

log = logging.getLogger("cobalt.tools")


@tool
def find_document(
    shipment_id: Annotated[str, "Shipment ID: SH- followed by four digits"],
    document_type: Annotated[str, "Document type: 'bill of lading', 'commercial invoice' or 'packing list'"],
) -> dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against."""
    try:
        document = store.search(shipment_id, document_type, timeout=args.tool_timeout)
    except TimeoutError as error:
        log.warning("find_document(%s, %s) failed: %s", shipment_id, document_type, error)
        return {
            "error": f"The document store did not answer within {args.tool_timeout:g} seconds, so the search did not finish.",
            "document_exists": "unknown",
            "advice": "Do not conclude that the document is missing. Report that this check could not be done.",
        }
    return document or {"found": False, "message": f"No {document_type} on file for {shipment_id}"}


store.behavior = "slow"
agent = investigator([get_shipment_status, get_customs_case, list_required_documents, find_document])
agent.client.function_invocation_configuration["max_duration_seconds"] = args.duration_limit


async def run():
    try:
        async with asyncio.timeout(args.run_timeout):  # None means no limit
            show(await agent.run(TASK))
    except TimeoutError:
        print("No answer: the program stopped waiting for the run.")
    print(f"\nThe program waited {time.monotonic() - start:.0f} seconds for the run.")


print(f"Task: {TASK}  (the document store takes {SLOW_SECONDS} seconds to answer)\n")
start = time.monotonic()
asyncio.run(run())
# asyncio.run waits (up to five minutes) for the threads it started, so a tool call still running keeps the program alive.
print(f"The program ended after {time.monotonic() - start:.0f} seconds.")
