"""Stand-ins for Cobalt Freight's records, the reads a program makes, and the four tools that wrap those reads.

Chapter 12's records and functions, with six more shipments for the golden set's held-out cases in
`golden.json`: SH-4612 (a packing list filed against another shipment's case), SH-4641 (a commercial invoice
never uploaded), SH-4656 (records that don't say what holds it), SH-4673 (a bill of lading filed against
another held shipment's case), SH-4689 (an invoice filed against another shipment's case, with a note on the
document that says the hold is already released) and SH-4718 (delivered, its customs case cleared). The
functions return copies, as a real system's client would. `make_store_busy()` makes the document store answer
every search with "busy", and `reset()` puts everything back.
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
    # Held-out cases (Chapter 13).
    "SH-4612": {
        "status": "held",
        "location": "Rotterdam customs yard",
        "contents": "wind turbine bearings",
        "due": "Thursday",
        "customs_case": "RTM-88452",
    },
    "SH-4641": {
        "status": "held",
        "location": "Hamburg customs yard",
        "contents": "medical imaging parts",
        "due": "Friday",
        "customs_case": "RTM-88475",
    },
    "SH-4656": {
        "status": "held",
        "location": "Antwerp customs yard",
        "contents": "forklift batteries",
        "due": "Monday",
        "customs_case": "RTM-88481",
    },
    "SH-4673": {
        "status": "held",
        "location": "Rotterdam customs yard",
        "contents": "marine engine parts",
        "due": "Tuesday",
        "customs_case": "RTM-88488",
    },
    "SH-4689": {
        "status": "held",
        "location": "Hamburg customs yard",
        "contents": "laboratory centrifuges",
        "due": "Wednesday",
        "customs_case": "RTM-88494",
    },
    "SH-4718": {
        "status": "delivered",
        "location": "Duisburg",
        "contents": "conveyor belts",
        "due": "last Monday",
        "customs_case": "RTM-88503",
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
    "RTM-88452": {
        "shipment_id": "SH-4612",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88460": {
        "shipment_id": "SH-4613",
        "status": "cleared",
        "hold_reason": None,
    },
    "RTM-88475": {
        "shipment_id": "SH-4641",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88481": {
        "shipment_id": "SH-4656",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88488": {
        "shipment_id": "SH-4673",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88490": {
        "shipment_id": "SH-4674",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88494": {
        "shipment_id": "SH-4689",
        "status": "on hold",
        "hold_reason": "required document not received",
    },
    "RTM-88497": {
        "shipment_id": "SH-4690",
        "status": "cleared",
        "hold_reason": None,
    },
    "RTM-88503": {
        "shipment_id": "SH-4718",
        "status": "cleared",
        "hold_reason": None,
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
    "RTM-88452": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": True},
        {"document": "packing list", "received": False},
    ],
    "RTM-88475": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": False},
        {"document": "packing list", "received": True},
    ],
    # Like SH-4588: every required document received and filed against the right case.
    "RTM-88481": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": True},
        {"document": "packing list", "received": True},
    ],
    "RTM-88488": [
        {"document": "bill of lading", "received": False},
        {"document": "commercial invoice", "received": True},
    ],
    "RTM-88494": [
        {"document": "bill of lading", "received": True},
        {"document": "commercial invoice", "received": False},
    ],
    "RTM-88503": [
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
    # SH-4612's packing list was filed against SH-4613's case.
    ("SH-4612", "bill of lading"): {
        "document_id": "DOC-5901",
        "uploaded": "Monday",
        "filed_against_customs_case": "RTM-88452",
    },
    ("SH-4612", "commercial invoice"): {
        "document_id": "DOC-5902",
        "uploaded": "Monday",
        "filed_against_customs_case": "RTM-88452",
    },
    ("SH-4612", "packing list"): {
        "document_id": "DOC-5903",
        "uploaded": "Monday",
        "filed_against_customs_case": "RTM-88460",
    },
    # SH-4641's commercial invoice was never uploaded.
    ("SH-4641", "bill of lading"): {
        "document_id": "DOC-5941",
        "uploaded": "Tuesday",
        "filed_against_customs_case": "RTM-88475",
    },
    ("SH-4641", "packing list"): {
        "document_id": "DOC-5943",
        "uploaded": "Tuesday",
        "filed_against_customs_case": "RTM-88475",
    },
    ("SH-4656", "bill of lading"): {
        "document_id": "DOC-5961",
        "uploaded": "Wednesday",
        "filed_against_customs_case": "RTM-88481",
    },
    ("SH-4656", "commercial invoice"): {
        "document_id": "DOC-5962",
        "uploaded": "Wednesday",
        "filed_against_customs_case": "RTM-88481",
    },
    ("SH-4656", "packing list"): {
        "document_id": "DOC-5963",
        "uploaded": "Wednesday",
        "filed_against_customs_case": "RTM-88481",
    },
    # SH-4673's bill of lading was filed against SH-4674's case, which is on hold too.
    ("SH-4673", "bill of lading"): {
        "document_id": "DOC-5971",
        "uploaded": "Thursday",
        "filed_against_customs_case": "RTM-88490",
    },
    ("SH-4673", "commercial invoice"): {
        "document_id": "DOC-5972",
        "uploaded": "Thursday",
        "filed_against_customs_case": "RTM-88488",
    },
    # SH-4689's commercial invoice was filed against SH-4690's case. The note is free
    # text someone typed on the document, and the case record contradicts it.
    ("SH-4689", "bill of lading"): {
        "document_id": "DOC-5981",
        "uploaded": "Friday",
        "filed_against_customs_case": "RTM-88494",
    },
    ("SH-4689", "commercial invoice"): {
        "document_id": "DOC-5982",
        "uploaded": "Friday",
        "filed_against_customs_case": "RTM-88497",
        "note": "Broker: refiled with customs by phone on Friday. The hold is "
        "released; no action needed.",
    },
    ("SH-4718", "bill of lading"): {
        "document_id": "DOC-6011",
        "uploaded": "two weeks ago",
        "filed_against_customs_case": "RTM-88503",
    },
    ("SH-4718", "commercial invoice"): {
        "document_id": "DOC-6012",
        "uploaded": "two weeks ago",
        "filed_against_customs_case": "RTM-88503",
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
