"""Chapter 8 demo: an audit record written inside each tool, and a fifth tool added without one."""

import asyncio
from datetime import datetime, timezone

from agent_framework import tool

import audit_store
import cobalt
from investigate import USER_ID, WITH_UPDATE, investigator, show


def audit(tool_name: str, **arguments) -> None:
    audit_store.write({
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": USER_ID,
        "tool": tool_name,
        "arguments": arguments,
    })


@tool
def get_shipment_status(shipment_id: str) -> dict:
    """Look up one shipment's status, location, contents, due day and customs case ID (if any)."""
    audit("get_shipment_status", shipment_id=shipment_id)
    return cobalt.get_shipment_status.func(shipment_id)


@tool
def get_customs_case(case_id: str) -> dict:
    """Look up a customs case: which shipment it belongs to, its status and why it is on hold."""
    audit("get_customs_case", case_id=case_id)
    return cobalt.get_customs_case.func(case_id)


@tool
def list_required_documents(case_id: str) -> object:
    """List the documents a customs case requires and whether customs has received each one."""
    audit("list_required_documents", case_id=case_id)
    return cobalt.list_required_documents.func(case_id)


@tool
def find_document(shipment_id: str, document_type: str) -> dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against."""
    audit("find_document", shipment_id=shipment_id, document_type=document_type)
    return cobalt.find_document.func(shipment_id, document_type)


# Added later, for customer updates. Nobody added the audit line.
tools = [get_shipment_status, get_customs_case, list_required_documents, find_document, cobalt.get_customer_contact]

audit_store.clear()
agent = investigator(tools=tools)
print(f"Task: {WITH_UPDATE}\n")
show(asyncio.run(agent.run(WITH_UPDATE)))
print()
audit_store.show()
