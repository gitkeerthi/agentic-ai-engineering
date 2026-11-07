"""Stand-ins for Cobalt Freight's systems, and the four tools that call them.

The records are Chapter 4's, plus three more of SH-4471's documents: the two customs has received, and a
certificate of origin (where the goods were made) that the case does not require.
What changes is where they live: each tool now calls a stand-in system instead of reading a
dictionary, and each system can be switched to misbehave the way running services do.
"""

import time
from typing import Annotated

from agent_framework import tool
from pydantic import BaseModel

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

SLOW_SECONDS = 20


class System:
    """A system the tools call. Set `behavior` to make it misbehave: "down", "flaky" or "slow"."""

    def __init__(self, name: str, host: str):
        self.name = name
        self.host = host
        self.reset()

    def reset(self) -> None:
        self.behavior = "normal"
        self.version = 1
        self.calls = 0

    def _connect(self, timeout: float | None) -> None:
        """What happens before a call returns data. With no timeout, a call waits as long as it takes."""
        self.calls += 1
        if self.behavior == "down" or (self.behavior == "flaky" and self.calls <= 2):
            raise ConnectionError(f"{self.name}: connection refused by {self.host}")
        if self.behavior == "slow":
            time.sleep(SLOW_SECONDS if timeout is None else min(SLOW_SECONDS, timeout))
            if timeout is not None and timeout < SLOW_SECONDS:
                raise TimeoutError(f"{self.name}: no response from {self.host} within {timeout} seconds")


class ShipmentTracker(System):
    def shipment(self, shipment_id: str, timeout: float | None = None) -> dict | None:
        self._connect(timeout)
        return SHIPMENTS.get(shipment_id)


class CustomsSystem(System):
    def case(self, case_id: str, timeout: float | None = None) -> dict | None:
        self._connect(timeout)
        return CUSTOMS_CASES.get(case_id)

    def required_documents(self, case_id: str, timeout: float | None = None) -> list[dict] | None:
        self._connect(timeout)
        documents = REQUIRED_DOCUMENTS.get(case_id)
        if documents and self.version == 2:
            # Version 2 of the customs system reports each document's status as a word, under a new name.
            return [{"document": d["document"], "status": "received" if d["received"] else "awaited"} for d in documents]
        return documents


class DocumentStore(System):
    def search(self, shipment_id: str, document_type: str, timeout: float | None = None) -> dict | None:
        self._connect(timeout)
        document = DOCUMENTS.get((shipment_id, document_type.lower()))
        if document and self.version == 2:
            # Version 2 of the document store renames the case field.
            return {"document_id": document["document_id"], "uploaded": document["uploaded"],
                    "case": document["filed_against_customs_case"]}
        return document


tracker = ShipmentTracker("shipment tracker", "tracker-01:8443")
customs = CustomsSystem("customs system", "customs-gw-03:443")
store = DocumentStore("document store", "docs-db-02:5432")


def reset() -> None:
    """Put every system back to normal, with its call count at zero."""
    for system in (tracker, customs, store):
        system.reset()


# The tools as a developer might first write them: a system's error, or Pydantic's rejection of its
# answer, passes straight through to the framework. Later programs replace them one at a time.


@tool
def get_shipment_status(shipment_id: Annotated[str, "Shipment ID: SH- followed by four digits"]) -> dict:
    """Look up one shipment's status, location, contents, due day and customs case ID (if any)."""
    return tracker.shipment(shipment_id) or {"error": f"No shipment found with ID {shipment_id}"}


@tool
def get_customs_case(case_id: Annotated[str, "Customs case ID: RTM- followed by five digits"]) -> dict:
    """Look up a customs case: which shipment it belongs to, its status and why it is on hold."""
    return customs.case(case_id) or {"error": f"No customs case found with ID {case_id}"}


class RequiredDocument(BaseModel):
    document: str
    received: bool


class RequiredDocuments(BaseModel):
    """What the tool returns. Pydantic checks the customs system's answer against it and drops any other fields."""

    case_id: str
    documents: list[RequiredDocument]


@tool
def list_required_documents(case_id: Annotated[str, "Customs case ID: RTM- followed by five digits"]) -> RequiredDocuments | dict:
    """List the documents a customs case requires and whether customs has received each one."""
    documents = customs.required_documents(case_id)
    if not documents:
        return {"error": f"No document list for case {case_id}"}
    return RequiredDocuments.model_validate({"case_id": case_id, "documents": documents})


@tool
def find_document(
    shipment_id: Annotated[str, "Shipment ID: SH- followed by four digits"],
    document_type: Annotated[str, "Document type: 'bill of lading', 'commercial invoice' or 'packing list'"],
) -> dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against."""
    return store.search(shipment_id, document_type) or {
        "found": False,
        "message": f"No {document_type} on file for {shipment_id}",
    }


TOOLS = [get_shipment_status, get_customs_case, list_required_documents, find_document]
