"""Stand-ins for Cobalt Freight's records, the four tools that read them, and the changes made to them later.

The records and tools are Chapter 6's. `release_sh4471()` changes the records the way the team's fix would,
`pick_up_sh4471()` the way the carrier's collection would, and `reset()` puts them back.
"""

import copy
from typing import Annotated

from agent_framework import tool
from pydantic import BaseModel, Field

SHIPMENTS = {
    "SH-4471": {
        "status": "held",
        "location": "Rotterdam customs yard",
        "contents": "industrial pumps",
        "due": "Friday",
        "customs_case": "RTM-88213",
    },
    "SH-5120": {
        "status": "in transit",
        "location": "Singapore",
        "contents": "valve assemblies",
        "due": "next Wednesday",
        "customs_case": None,
    },
}

CUSTOMS_CASES = {
    "RTM-88213": {"shipment_id": "SH-4471", "status": "on hold", "hold_reason": "required document not received"},
    "RTM-88124": {"shipment_id": "SH-4398", "status": "cleared", "hold_reason": None},
}

REQUIRED_DOCUMENTS = {
    "RTM-88213": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": False},
        {"document": "packing list", "received": True},
    ],
}

# SH-4471's invoice exists, but it was filed against another shipment's customs case.
DOCUMENTS = {
    ("SH-4471", "bill of lading"): {"document_id": "DOC-5529", "uploaded": "Thursday", "filed_against_customs_case": "RTM-88213"},
    ("SH-4471", "commercial invoice"): {"document_id": "DOC-5531", "uploaded": "Thursday", "filed_against_customs_case": "RTM-88124"},
    ("SH-4471", "packing list"): {"document_id": "DOC-5530", "uploaded": "Thursday", "filed_against_customs_case": "RTM-88213"},
    ("SH-4471", "certificate of origin"): {"document_id": "DOC-5532", "uploaded": "Thursday", "filed_against_customs_case": None},
    ("SH-5120", "commercial invoice"): {"document_id": "DOC-6102", "uploaded": "last Tuesday", "filed_against_customs_case": None},
    ("SH-5120", "bill of lading"): {"document_id": "DOC-6103", "uploaded": "last Tuesday", "filed_against_customs_case": None},
    ("SH-5120", "packing list"): {"document_id": "DOC-6104", "uploaded": "last Tuesday", "filed_against_customs_case": None},
}


@tool
def get_shipment_status(shipment_id: Annotated[str, "Shipment ID: SH- followed by four digits"]) -> dict:
    """Look up one shipment's status, location, contents, due day and customs case ID (if any)."""
    return SHIPMENTS.get(shipment_id) or {"error": f"No shipment found with ID {shipment_id}"}


@tool
def get_customs_case(case_id: Annotated[str, "Customs case ID: RTM- followed by five digits"]) -> dict:
    """Look up a customs case: which shipment it belongs to, its status and why it is on hold."""
    return CUSTOMS_CASES.get(case_id) or {"error": f"No customs case found with ID {case_id}"}


class RequiredDocument(BaseModel):
    document: str
    received: bool


class RequiredDocuments(BaseModel):
    case_id: str
    documents: list[RequiredDocument]


@tool
def list_required_documents(case_id: Annotated[str, "Customs case ID: RTM- followed by five digits"]) -> RequiredDocuments | dict:
    """List the documents a customs case requires and whether customs has received each one."""
    documents = REQUIRED_DOCUMENTS.get(case_id)
    if not documents:
        return {"error": f"No document list for case {case_id}"}
    return RequiredDocuments(case_id=case_id, documents=documents)


@tool
def find_document(
    shipment_id: Annotated[str, Field(pattern=r"^SH-\d{4}$", description="Shipment ID: SH- followed by four digits")],
    document_type: Annotated[str, "Document type in plain words. The store holds more types than any one customs case requires."],
) -> dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against."""
    return DOCUMENTS.get((shipment_id, document_type.lower())) or {
        "found": False,
        "message": f"No {document_type} on file for {shipment_id}",
    }


TOOLS = [get_shipment_status, get_customs_case, list_required_documents, find_document]

_ORIGINAL = copy.deepcopy((SHIPMENTS, CUSTOMS_CASES, REQUIRED_DOCUMENTS, DOCUMENTS))


def reset() -> None:
    """Put every record back as it was before the fix."""
    for records, original in zip((SHIPMENTS, CUSTOMS_CASES, REQUIRED_DOCUMENTS, DOCUMENTS), _ORIGINAL):
        records.clear()
        records.update(copy.deepcopy(original))


def release_sh4471() -> None:
    """The team refiles the invoice against SH-4471's case; customs receives it, clears the case and releases the shipment."""
    DOCUMENTS[("SH-4471", "commercial invoice")]["filed_against_customs_case"] = "RTM-88213"
    REQUIRED_DOCUMENTS["RTM-88213"][1]["received"] = True
    CUSTOMS_CASES["RTM-88213"].update(status="cleared", hold_reason=None)
    SHIPMENTS["SH-4471"].update(status="released", location="Rotterdam customs yard, awaiting pickup")


def pick_up_sh4471() -> None:
    """After release, the carrier collects SH-4471 from the yard."""
    SHIPMENTS["SH-4471"].update(status="in transit", location="on a truck to Duisburg")
