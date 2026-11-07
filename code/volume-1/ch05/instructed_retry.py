"""Chapter 5 demo: the document store is down, and the agent's instructions, not the tool's result, say when to stop calling it."""

import asyncio
import logging
from typing import Annotated

from agent_framework import tool

from cobalt import get_customs_case, get_shipment_status, list_required_documents, store
from investigate import TASK, investigator, show

INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight's operations team.

Goal: find the root cause of a delay and the action that would fix it.

How to work:
- Use the tools to check facts. Never guess a status, case number or document location.
- Before each tool call, say in one sentence what you want to find out.
- A hold or a delay is a symptom. Keep investigating until you find what caused it,
  or until no tool can tell you more.
- If a tool reports that a system did not respond, do not call that tool again in this
  investigation. Report that the check could not be done.

Limits:
- You can only read Cobalt's systems. Recommend actions; never claim to have taken one.

Answer format:
Cause: one sentence.
Evidence: the facts that show it, with IDs.
Recommended action: one sentence."""

log = logging.getLogger("cobalt.tools")


# The same tool as written_error.py: its result says what the failure means, but not whether to search again.
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
agent = investigator([get_shipment_status, get_customs_case, list_required_documents, find_document], INSTRUCTIONS)
print(f"Task: {TASK}  (the document store is down; the instructions say not to call a failed tool again)\n")
show(asyncio.run(agent.run(TASK)))
