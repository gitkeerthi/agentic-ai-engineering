"""Findings the tests use, as an agent would report them for the seeded shipments."""


def misfiled_invoice(**changes) -> dict:
    finding = {
        "shipment_id": "SH-4471",
        "status": "cause_found",
        "cause": "The commercial invoice DOC-5531 is filed against RTM-88124, another shipment's case.",
        "fault": {
            "document": "commercial invoice",
            "problem": "filed_against_another_case",
        },
        "evidence": [
            {
                "record_id": "RTM-88213",
                "fact": "the commercial invoice is not received",
            },
            {"record_id": "DOC-5531", "fact": "filed against RTM-88124"},
        ],
        "recommended_action": "Refile DOC-5531 against RTM-88213.",
        "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"},
    }
    return finding | changes


def rejected_invoice(**changes) -> dict:
    finding = {
        "shipment_id": "SH-4731",
        "status": "cause_found",
        "cause": "Customs rejected the commercial invoice DOC-6042 because it isn't signed.",
        "fault": {
            "document": "commercial invoice",
            "problem": "rejected_by_customs",
        },
        "evidence": [
            {
                "record_id": "MSG-7104",
                "fact": "customs rejected DOC-6042: not signed",
            },
            {
                "record_id": "RTM-88520",
                "fact": "the commercial invoice is not received",
            },
        ],
        "recommended_action": "Obtain a signed commercial invoice and file it against RTM-88520.",
        "refiling": None,
    }
    return finding | changes


def undetermined(shipment_id: str, record_id: str) -> dict:
    return {
        "shipment_id": shipment_id,
        "status": "undetermined",
        "cause": None,
        "fault": None,
        "evidence": [
            {
                "record_id": record_id,
                "fact": "on hold, every required document received",
            }
        ],
        "recommended_action": "Ask customs what the case is waiting for.",
        "refiling": None,
        "open_question": "What is customs still waiting for?",
    }


def case_file(shipment_id: str):
    """The case file the workflow's reads would gather for a seeded shipment."""
    from cobalt_exceptions.domain.contracts import CaseFile
    from cobalt_exceptions.systems import records

    shipment = records.shipment_status(shipment_id)
    case_id = shipment["customs_case"]
    required = records.required_documents(case_id)
    filings = {
        r["document"]: records.document_search(shipment_id, r["document"])
        for r in required
    }
    others = {f["filed_against_customs_case"] for f in filings.values()} - {
        None,
        case_id,
    }
    other_cases = {c: records.customs_case(c) for c in sorted(others)}
    return CaseFile(
        shipment_id,
        shipment,
        case_id,
        records.customs_case(case_id),
        required,
        filings,
        other_cases,
    )
