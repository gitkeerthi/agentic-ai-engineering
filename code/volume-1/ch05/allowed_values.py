"""Chapter 5 demo: a tool that accepts only three document types, asked about a fourth."""

import argparse
import asyncio
import json
from typing import Annotated, Literal

from agent_framework import tool
from pydantic import Field

import cobalt
from cobalt import get_customs_case, get_shipment_status, list_required_documents, store
from investigate import investigator, show


@tool
def find_document(
    shipment_id: Annotated[str, Field(pattern=r"^SH-\d{4}$", description="Shipment ID: SH- followed by four digits")],
    document_type: Annotated[Literal["bill of lading", "commercial invoice", "packing list"], "Document type"],
) -> dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against."""
    return store.search(shipment_id, document_type) or {
        "found": False,
        "message": f"No {document_type} on file for {shipment_id}",
    }


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--any-type", action="store_true", help="use cobalt.py's find_document, which takes any document type")
search = cobalt.find_document if parser.parse_args().any_type else find_document

print("The parameters the model is given for find_document:")
print(json.dumps(search.parameters()["properties"], indent=2))

task = "Customs now also wants a certificate of origin for shipment 4471. Does Cobalt hold one?"
agent = investigator([get_shipment_status, get_customs_case, list_required_documents, search])
print(f"\nTask: {task}\n")
show(asyncio.run(agent.run(task)))
