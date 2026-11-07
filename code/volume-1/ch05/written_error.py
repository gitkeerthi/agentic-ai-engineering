"""Chapter 5 demo: the document store is down, and the tool tells the model what the failure means."""

import asyncio
import logging
from typing import Annotated

from agent_framework import tool

from cobalt import get_customs_case, get_shipment_status, list_required_documents, store
from investigate import TASK, investigator, show

log = logging.getLogger("cobalt.tools")


@tool
def find_document(
    shipment_id: Annotated[str, "Shipment ID: SH- followed by four digits"],
    document_type: Annotated[str, "Document type: 'bill of lading', 'commercial invoice' or 'packing list'"],
) -> dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against."""
    try:
        document = store.search(shipment_id, document_type)
    except (ConnectionError, TimeoutError) as error:
        log.warning("find_document(%s, %s) failed: %s", shipment_id, document_type, error)
        return {
            "error": "The document store did not respond, so no search was made.",
            "document_exists": "unknown",
            "advice": "Do not conclude that the document is missing. Report that this check could not be done.",
        }
    return document or {"found": False, "message": f"No {document_type} on file for {shipment_id}"}


store.behavior = "down"
agent = investigator([get_shipment_status, get_customs_case, list_required_documents, find_document])
print(f"Task: {TASK}  (the document store is down)\n")
show(asyncio.run(agent.run(TASK)))
