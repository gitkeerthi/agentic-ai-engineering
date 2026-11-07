"""Stand-ins for the systems Cobalt doesn't own: its transport records, customs, and the document store.

Each function is what a client for the real system would offer. Reads return copies; the document
store's search can be busy, and its client retries a few times before giving up. `check_refile()` is
the store's own rule for a refiling; the write itself is in `filing.py`, which only the services may
import. Filing a document doesn't release the shipment: customs does that, in `customs_processes()`,
a lab stand-in for customs' own work.
"""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import storage

SEED = json.loads((Path(__file__).parent / "seed.json").read_text())


class Unavailable(ConnectionError):
    """The system didn't answer; what it holds is unknown."""


def reset() -> None:
    """Put every record back as seeded, with no filings and no lab faults."""
    records = copy.deepcopy(SEED)
    records |= {
        "filings": [],
        "completed": {},
        "busy": {"documents": 0, "messages": 0},
        "replies_to_drop": 0,
    }
    storage.save("records", records)


def load_records() -> dict:
    records = storage.load("records")
    if records is None:
        reset()
        records = storage.load("records")
    return records


def shipment_status(shipment_id: str) -> dict:
    found = load_records()["shipments"].get(shipment_id)
    return found or {"error": f"No shipment found with ID {shipment_id}"}


def customs_case(case_id: str) -> dict:
    found = load_records()["customs_cases"].get(case_id)
    return found or {"error": f"No customs case found with ID {case_id}"}


def required_documents(case_id: str) -> list[dict] | None:
    return load_records()["required_documents"].get(case_id)


def answers_busy(system: str) -> bool:
    """A lab fault: the system answers "busy" to its next N requests."""
    records = load_records()
    if records["busy"][system] <= 0:
        return False
    records["busy"][system] -= 1
    storage.save("records", records)
    return True


RETRY = dict(
    retry=retry_if_exception_type(Unavailable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.05, max=0.5),
    reraise=True,
)


@retry(**RETRY)
def document_search(shipment_id: str, document_type: str) -> dict:
    """Where the store has a shipment's document of one type. Raises Unavailable after three tries."""
    if answers_busy("documents"):
        raise Unavailable("document store busy")
    for document_id, doc in load_records()["documents"].items():
        if (
            doc["shipment_id"] == shipment_id
            and doc["type"] == document_type.lower()
        ):
            found = {"document_id": document_id, **doc}
            del found["shipment_id"], found["type"]
            return found
    return {
        "found": False,
        "message": f"No {document_type} on file for {shipment_id}",
    }


def document(document_id: str) -> dict | None:
    return load_records()["documents"].get(document_id)


def check_refile(document_id: str, customs_case: str) -> str | None:
    """Why the store would refuse this refiling, or None if its rules allow it."""
    records = load_records()
    doc = records["documents"].get(document_id)
    case = records["customs_cases"].get(customs_case)
    if doc is None:
        return f"no document {document_id}"
    if case is None:
        return f"no customs case {customs_case}"
    if case["shipment_id"] != doc["shipment_id"]:
        return f"{customs_case} belongs to {case['shipment_id']}, not to {doc['shipment_id']}"
    if case["status"] != "on hold":
        return f"{customs_case} is {case['status']}; only a case on hold takes new filings"
    if doc["filed_against_customs_case"] == customs_case:
        return f"{document_id} is already filed against {customs_case}"
    return None


def customs_processes() -> list[str]:
    """Lab stand-in for customs: mark each filed document received, and clear each case on hold
    that a filing went to once its required documents have all been received. Returns the cases cleared."""
    records = load_records()
    cleared = []
    filed_to = {filing["customs_case"] for filing in records["filings"]}
    for filing in records["filings"]:
        doc = records["documents"][filing["document_id"]]
        for item in records["required_documents"].get(filing["customs_case"], []):
            if item["document"] == doc["type"]:
                item["received"] = True
    for case_id in sorted(filed_to):
        case = records["customs_cases"][case_id]
        required = records["required_documents"].get(case_id) or []
        if (
            case["status"] == "on hold"
            and required
            and all(r["received"] for r in required)
        ):
            case.update(status="cleared", hold_reason=None)
            records["shipments"][case["shipment_id"]]["status"] = "released"
            cleared.append(case_id)
    storage.save("records", records)
    return cleared


def make_busy(system: str, requests: int) -> None:
    """A lab fault: "documents" or "messages" answers busy to its next N requests."""
    records = load_records()
    records["busy"][system] = requests
    storage.save("records", records)


def drop_replies(times: int = 1) -> None:
    """A lab fault: the store's next filings succeed, but their replies are lost on the way back."""
    records = load_records()
    records["replies_to_drop"] = times
    storage.save("records", records)


def colleague_replaces(document_id: str) -> None:
    """A lab change: someone edits the document while a request waits, so its version moves on."""
    records = load_records()
    records["documents"][document_id]["version"] += 1
    storage.save("records", records)
