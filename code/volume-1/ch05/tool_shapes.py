"""Chapter 5 demo: the same investigation with three shapes of tool set, and what each run cost."""

import argparse
import asyncio
from typing import Annotated, Literal

from agent_framework import tool

from cobalt import TOOLS, customs, store, tracker
from investigate import TASK, investigator, show


@tool
def check_customs_documents(shipment_id: Annotated[str, "Shipment ID: SH- followed by four digits"]) -> dict:
    """Check a shipment's customs case in one step: the shipment, its customs case and hold reason, and each document the case requires, with whether customs has received it and where Cobalt's document store has it filed."""
    shipment = tracker.shipment(shipment_id)
    if not shipment:
        return {"error": f"No shipment found with ID {shipment_id}"}
    case_id = shipment["customs_case"]
    if not case_id:
        return {"shipment": shipment, "customs_case": None, "message": "The shipment has no customs case."}
    documents = []
    for required in customs.required_documents(case_id) or []:
        filed = store.search(shipment_id, required["document"])
        documents.append({
            "document": required["document"],
            "received_by_customs": required["received"],
            "in_document_store": filed or "not on file",
        })
    return {"shipment": shipment, "customs_case": {"case_id": case_id, **customs.case(case_id)}, "required_documents": documents}


@tool
def lookup(
    record_type: Annotated[Literal["shipment", "customs case", "required documents", "document"], "The kind of record"],
    key: Annotated[str, "The record's ID. For a document: the shipment ID and document type joined by a colon, such as SH-0000:packing list"],
) -> dict:
    """Look up any record in Cobalt's systems: a shipment, a customs case, the documents a case requires, or a document in the document store."""
    if record_type == "shipment":
        record = tracker.shipment(key)
    elif record_type == "customs case":
        record = customs.case(key)
    elif record_type == "required documents":
        record = customs.required_documents(key)
    else:
        shipment_id, _, document_type = key.partition(":")
        record = store.search(shipment_id.strip(), document_type.strip())
    return {"record": record} if record else {"error": f"No {record_type} found for {key}"}


SHAPES = {"narrow": TOOLS, "consolidated": [check_customs_documents], "generic": [lookup]}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("shape", choices=SHAPES, nargs="?", default="narrow")
shape = parser.parse_args().shape

agent = investigator(SHAPES[shape])
print(f"Task: {TASK}  ({shape} tools)\n")
result = asyncio.run(agent.run(TASK))
show(result)

model_calls = sum(1 for message in result.messages if message.role == "assistant")
print(f"\n{shape}: {model_calls} model calls, {result.usage_details['total_token_count']} tokens in total.")
