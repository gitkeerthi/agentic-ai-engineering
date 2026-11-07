"""Chapter 5 demo: the tool retries a failing store with a retry library, and the program counts the calls each layer made."""

import argparse
import asyncio
import logging
from typing import Annotated

from agent_framework import tool
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from cobalt import get_customs_case, get_shipment_status, list_required_documents, store
from investigate import TASK, investigator, show

ATTEMPTS = 3
STORE_TIMEOUT = 3  # seconds for each attempt

log = logging.getLogger("cobalt.tools")


@retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    stop=stop_after_attempt(ATTEMPTS),
    wait=wait_random_exponential(multiplier=0.5, max=4),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def search_store(shipment_id: str, document_type: str) -> dict | None:
    return store.search(shipment_id, document_type, timeout=STORE_TIMEOUT)


@tool
def find_document(
    shipment_id: Annotated[str, "Shipment ID: SH- followed by four digits"],
    document_type: Annotated[str, "Document type: 'bill of lading', 'commercial invoice' or 'packing list'"],
) -> dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against."""
    try:
        document = search_store(shipment_id, document_type)
    except (ConnectionError, TimeoutError) as error:
        log.error("find_document(%s, %s) failed after %d attempts: %s", shipment_id, document_type, ATTEMPTS, error)
        return {
            "error": f"The document store did not respond to {ATTEMPTS} attempts, so no search was made.",
            "document_exists": "unknown",
            "advice": "Do not search the document store again in this investigation. "
            "Do not conclude that the document is missing. Report that this check could not be done.",
        }
    return document or {"found": False, "message": f"No {document_type} on file for {shipment_id}"}


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--store", choices=["flaky", "down"], default="flaky", help="flaky: the first two calls fail")
store.behavior = parser.parse_args().store

agent = investigator([get_shipment_status, get_customs_case, list_required_documents, find_document])
print(f"Task: {TASK}  (the document store is {store.behavior})\n")
result = asyncio.run(agent.run(TASK))
show(result)

searches = sum(1 for m in result.messages for c in m.contents if c.type == "function_call" and c.name == "find_document")
print(f"\nThe model called find_document {searches} times; the tool called the store {store.calls} times.")
