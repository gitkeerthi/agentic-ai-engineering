"""Stand-ins for Cobalt Freight's records, the reads a program makes, and the four tools that wrap those reads.

Chapter 11's records and functions, with four more held shipments for the case set in `cases.json`: SH-4502
(a packing list never uploaded), SH-4533 (held for a physical inspection), SH-4560 (a bill of lading filed
against another shipment's case) and SH-4588 (records that don't say what holds it). The functions return
copies, as a real system's client would. `make_store_busy()` makes the document store answer every search
with "busy", and `reset()` puts everything back.
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
    "SH-4502": {
        "status": "held",
        "location": "Rotterdam customs yard",
        "contents": "solar inverters",
        "due": "Thursday",
        "customs_case": "RTM-88301",
    },
    "SH-4533": {
        "status": "held",
        "location": "Rotterdam customs yard",
        "contents": "lithium batteries",
        "due": "Monday",
        "customs_case": "RTM-88350",
    },
    "SH-4560": {
        "status": "held",
        "location": "Antwerp customs yard",
        "contents": "hydraulic valves",
        "due": "Tuesday",
        "customs_case": "RTM-88405",
    },
    "SH-4588": {
        "status": "held",
        "location": "Rotterdam customs yard",
        "contents": "printed circuit boards",
        "due": "Wednesday",
        "customs_case": "RTM-88377",
    },
}

CUSTOMS_CASES = {
    "RTM-88213": {
        "shipment_id": "SH-4471",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88124": {
        "shipment_id": "SH-4398",
        "status": "cleared",
        "hold_reason": None,
    },
    "RTM-88301": {
        "shipment_id": "SH-4502",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88350": {
        "shipment_id": "SH-4533",
        "status": "on hold",
        "hold_reason": "physical inspection",
    },
    "RTM-88405": {
        "shipment_id": "SH-4560",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88410": {
        "shipment_id": "SH-4561",
        "status": "cleared",
        "hold_reason": None,
    },
    "RTM-88377": {
        "shipment_id": "SH-4588",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
}

REQUIRED_DOCUMENTS = {
    "RTM-88213": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": False},
        {"document": "packing list", "received": True},
    ],
    "RTM-88301": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": True},
        {"document": "packing list", "received": False},
    ],
    "RTM-88350": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": True},
    ],
    "RTM-88405": [
        {"document": "bill of lading", "received": False},
        {"document": "commercial invoice", "received": True},
    ],
    # Every required document received and filed against the right case: the
    # records don't say what is holding SH-4588.
    "RTM-88377": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": True},
    ],
}

# SH-4471's invoice exists, but it was filed against another shipment's customs case.
DOCUMENTS = {
    ("SH-4471", "bill of lading"): {
        "document_id": "DOC-5529",
        "uploaded": "Thursday",
        "filed_against_customs_case": "RTM-88213",
    },
    ("SH-4471", "commercial invoice"): {
        "document_id": "DOC-5531",
        "uploaded": "Thursday",
        "filed_against_customs_case": "RTM-88124",
    },
    ("SH-4471", "packing list"): {
        "document_id": "DOC-5530",
        "uploaded": "Thursday",
        "filed_against_customs_case": "RTM-88213",
    },
    ("SH-4471", "certificate of origin"): {
        "document_id": "DOC-5532",
        "uploaded": "Thursday",
        "filed_against_customs_case": None,
    },
    ("SH-5120", "commercial invoice"): {
        "document_id": "DOC-6102",
        "uploaded": "last Tuesday",
        "filed_against_customs_case": None,
    },
    ("SH-5120", "bill of lading"): {
        "document_id": "DOC-6103",
        "uploaded": "last Tuesday",
        "filed_against_customs_case": None,
    },
    ("SH-5120", "packing list"): {
        "document_id": "DOC-6104",
        "uploaded": "last Tuesday",
        "filed_against_customs_case": None,
    },
    # SH-4502's packing list was never uploaded.
    ("SH-4502", "bill of lading"): {
        "document_id": "DOC-5601",
        "uploaded": "Monday",
        "filed_against_customs_case": "RTM-88301",
    },
    ("SH-4502", "commercial invoice"): {
        "document_id": "DOC-5602",
        "uploaded": "Monday",
        "filed_against_customs_case": "RTM-88301",
    },
    ("SH-4533", "bill of lading"): {
        "document_id": "DOC-5651",
        "uploaded": "Friday",
        "filed_against_customs_case": "RTM-88350",
    },
    ("SH-4533", "commercial invoice"): {
        "document_id": "DOC-5652",
        "uploaded": "Friday",
        "filed_against_customs_case": "RTM-88350",
    },
    # SH-4560's bill of lading was filed against SH-4561's case.
    ("SH-4560", "bill of lading"): {
        "document_id": "DOC-5711",
        "uploaded": "Wednesday",
        "filed_against_customs_case": "RTM-88410",
    },
    ("SH-4560", "commercial invoice"): {
        "document_id": "DOC-5712",
        "uploaded": "Wednesday",
        "filed_against_customs_case": "RTM-88405",
    },
    ("SH-4588", "bill of lading"): {
        "document_id": "DOC-5801",
        "uploaded": "Tuesday",
        "filed_against_customs_case": "RTM-88377",
    },
    ("SH-4588", "commercial invoice"): {
        "document_id": "DOC-5802",
        "uploaded": "Tuesday",
        "filed_against_customs_case": "RTM-88377",
    },
}

store = {"busy": False}


def shipment_status(shipment_id: str) -> dict:
    return copy.deepcopy(SHIPMENTS.get(shipment_id)) or {
        "error": f"No shipment found with ID {shipment_id}"
    }


def customs_case(case_id: str) -> dict:
    return copy.deepcopy(CUSTOMS_CASES.get(case_id)) or {
        "error": f"No customs case found with ID {case_id}"
    }


def required_documents(case_id: str) -> list[dict] | None:
    return copy.deepcopy(REQUIRED_DOCUMENTS.get(case_id))


def document_search(shipment_id: str, document_type: str) -> dict:
    if store["busy"]:
        return {"error": "Document store busy. Try again."}
    return copy.deepcopy(DOCUMENTS.get((shipment_id, document_type.lower()))) or {
        "found": False,
        "message": f"No {document_type} on file for {shipment_id}",
    }


@tool
def get_shipment_status(
    shipment_id: Annotated[str, "Shipment ID: SH- followed by four digits"],
) -> dict:
    """Look up one shipment's status, location, contents, due day and customs case ID (if any)."""
    return shipment_status(shipment_id)


@tool
def get_customs_case(
    case_id: Annotated[str, "Customs case ID: RTM- followed by five digits"],
) -> dict:
    """Look up a customs case: which shipment it belongs to, its status and why it is on hold."""
    return customs_case(case_id)


class RequiredDocument(BaseModel):
    document: str
    received: bool


class RequiredDocuments(BaseModel):
    case_id: str
    documents: list[RequiredDocument]


@tool
def list_required_documents(
    case_id: Annotated[str, "Customs case ID: RTM- followed by five digits"],
) -> RequiredDocuments | dict:
    """List the documents a customs case requires and whether customs has received each one."""
    documents = required_documents(case_id)
    if not documents:
        return {"error": f"No document list for case {case_id}"}
    return RequiredDocuments(case_id=case_id, documents=documents)


@tool
def find_document(
    shipment_id: Annotated[
        str,
        Field(
            pattern=r"^SH-\d{4}$",
            description="Shipment ID: SH- followed by four digits",
        ),
    ],
    document_type: Annotated[
        str,
        "Document type in plain words. The store holds more types than any one customs case requires.",
    ],
) -> dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against."""
    return document_search(shipment_id, document_type)


TOOLS = [
    get_shipment_status,
    get_customs_case,
    list_required_documents,
    find_document,
]

_ORIGINAL = copy.deepcopy((SHIPMENTS, CUSTOMS_CASES, REQUIRED_DOCUMENTS, DOCUMENTS))


def reset() -> None:
    """Put every record back, and the document store back to normal."""
    for records, original in zip(
        (SHIPMENTS, CUSTOMS_CASES, REQUIRED_DOCUMENTS, DOCUMENTS), _ORIGINAL
    ):
        records.clear()
        records.update(copy.deepcopy(original))
    store["busy"] = False


def make_store_busy() -> None:
    """The document store answers every search with "busy"."""
    store["busy"] = True
