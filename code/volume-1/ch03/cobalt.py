"""Stand-ins for Cobalt Freight's systems, and the tool descriptions the model sees for them.

A shipment (SH-) that crosses a border gets a customs case (RTM-), which lists the documents customs needs.
Customs receives a document (DOC-) only when it is filed against that case.
"""

from agentlab.llm import describe_tool

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

# SH-4471's invoice exists, but it was uploaded against another shipment's customs case.
# SH-5120 has not reached customs yet, so its documents are not filed against any case.
DOCUMENTS = {
    ("SH-4471", "commercial invoice"): {
        "document_id": "DOC-5531",
        "uploaded": "Thursday",
        "filed_against_customs_case": "RTM-88124",
    },
    ("SH-5120", "commercial invoice"): {"document_id": "DOC-6102", "uploaded": "last Tuesday", "filed_against_customs_case": None},
    ("SH-5120", "bill of lading"): {"document_id": "DOC-6103", "uploaded": "last Tuesday", "filed_against_customs_case": None},
    ("SH-5120", "packing list"): {"document_id": "DOC-6104", "uploaded": "last Tuesday", "filed_against_customs_case": None},
}


def get_shipment_status(shipment_id: str) -> dict:
    return SHIPMENTS.get(shipment_id) or {"error": f"No shipment found with ID {shipment_id}"}


def get_customs_case(case_id: str) -> dict:
    return CUSTOMS_CASES.get(case_id) or {"error": f"No customs case found with ID {case_id}"}


def list_required_documents(case_id: str) -> dict:
    documents = REQUIRED_DOCUMENTS.get(case_id)
    return {"case_id": case_id, "documents": documents} if documents else {"error": f"No document list for case {case_id}"}


def find_document(shipment_id: str, document_type: str) -> dict:
    return DOCUMENTS.get((shipment_id, document_type.lower())) or {
        "found": False,
        "message": f"No {document_type} on file for {shipment_id}",
    }


TOOLS = {
    "get_shipment_status": get_shipment_status,
    "get_customs_case": get_customs_case,
    "list_required_documents": list_required_documents,
    "find_document": find_document,
}


# The example IDs here are real records. Chapter 3 shows why that is a mistake; Chapter 5 fixes it.
TOOL_DESCRIPTIONS = [
    describe_tool(
        "get_shipment_status",
        "Look up one shipment's status, location, contents, due day and customs case ID (if any).",
        shipment_id="Shipment ID, for example SH-4471",
    ),
    describe_tool(
        "get_customs_case",
        "Look up a customs case: which shipment it belongs to, its status and why it is on hold.",
        case_id="Customs case ID, for example RTM-88213",
    ),
    describe_tool(
        "list_required_documents",
        "List the documents a customs case requires and whether customs has received each one.",
        case_id="Customs case ID, for example RTM-88213",
    ),
    describe_tool(
        "find_document",
        "Search Cobalt's document store for a shipment's document. "
        "Returns where it is filed, including the customs case it was uploaded against.",
        shipment_id="Shipment ID, for example SH-4471",
        document_type="Document type, for example 'commercial invoice'",
    ),
]
