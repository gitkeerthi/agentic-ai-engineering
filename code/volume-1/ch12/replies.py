"""Findings the tests script the agent to report, so each test controls the model's side of the run.

BUSY_STORE_FINDING is a real reply, copied from a run of the workflow with the_change.py's edit and the store
busy (run 5 of five). It reads well and passes the finding check, and it is wrong: the invoice is on file,
filed against another shipment's case.
"""

SUPPORTED = {
    "shipment_id": "SH-4471",
    "status": "cause_found",
    "cause": "The commercial invoice is filed against customs case RTM-88124 instead of RTM-88213.",
    "evidence": [
        {"record_id": "DOC-5531", "fact": "Filed against RTM-88124."},
        {
            "record_id": "RTM-88213",
            "fact": "On hold: required document not received.",
        },
    ],
    "recommended_action": "Refile DOC-5531 against RTM-88213.",
    "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"},
}

BUSY_STORE_FINDING = {
    "shipment_id": "SH-4471",
    "status": "cause_found",
    "cause": "The customs case RTM-88213 is on hold because the required commercial "
    "invoice has not been received.",
    "evidence": [
        {
            "record_id": "RTM-88213",
            "fact": "The case status is on hold with hold reason 'required document "
            "not received'.",
        },
        {
            "record_id": "SH-4471",
            "fact": "The shipment's required documents list shows the commercial "
            "invoice with received: false, while the bill of lading and packing "
            "list are received.",
        },
    ],
    "recommended_action": "Obtain and submit the missing commercial invoice for "
    "customs case RTM-88213 so the hold can be lifted.",
    "refiling": None,
}


def report(finding: dict, call_id: str = "call_1") -> tuple:
    """One scripted model reply: a report_finding call with these arguments."""
    return ("report_finding", finding, call_id)
