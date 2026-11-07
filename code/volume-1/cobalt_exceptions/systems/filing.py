"""The document store's write API (Chapter 9's): a refiling with the store's own rules, a
compare-and-set on the document's version, an idempotency key, and the approver recorded with the
filing. A module of its own so that the dependency rule can say who may file: only the services.
"""

from datetime import UTC, datetime

from . import storage
from .records import check_refile, load_records


class ReplyLost(ConnectionError):
    """The store did the work, but its reply never reached the caller."""


def refile(
    document_id: str,
    customs_case: str,
    expected_version: int,
    key: str,
    approved_by: str,
) -> dict:
    """Submit a new filing of a document against a customs case.

    expected_version: refuse if the document changed since the request was made (compare-and-set).
    key: an idempotency key; a second request with the same key gets the first one's answer.
    """
    records = load_records()
    if key in records["completed"]:
        return _reply(records, records["completed"][key])
    doc = records["documents"].get(document_id)
    if doc and doc["version"] != expected_version:
        return {
            "error": "conflict",
            "message": f"{document_id} is at version {doc['version']}, not {expected_version}",
        }
    if reason := check_refile(document_id, customs_case):
        return {"error": "refused", "message": reason}
    doc["filed_against_customs_case"] = customs_case
    doc["version"] += 1
    filing = f"FIL-{len(records['filings']) + 1:03d}"
    now = datetime.now(UTC).isoformat(timespec="seconds")
    records["filings"].append(
        {
            "filing": filing,
            "document_id": document_id,
            "customs_case": customs_case,
            "approved_by": approved_by,
            "key": key,
            "time": now,
        }
    )
    answer = {
        "filing": filing,
        "document_id": document_id,
        "now_filed_against": customs_case,
        "version": doc["version"],
    }
    records["completed"][key] = answer
    return _reply(records, answer)


def _reply(records: dict, answer: dict) -> dict:
    lost = records["replies_to_drop"] > 0
    records["replies_to_drop"] = max(0, records["replies_to_drop"] - 1)
    storage.save("records", records)
    if lost:  # a lab fault: whatever the store did is saved, then the connection drops
        raise ReplyLost("connection reset before the store replied")
    return answer


def outcome_of(key: str) -> dict | None:
    """The store's answer to the filing made under this idempotency key, if it made one."""
    return load_records()["completed"].get(key)
