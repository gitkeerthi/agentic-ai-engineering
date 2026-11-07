"""Cobalt's case system: one record per investigation request, with its state and every move it made.

The case system is the system of record for where a case stands. Every move goes through the
domain's lifecycle, which refuses moves it doesn't allow, and is kept as an event with who made it,
on whose authority, and the trace ID of the run behind it.
"""

from datetime import UTC, datetime

from ..domain.lifecycle import move
from . import storage


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _all() -> dict:
    return storage.load("cases", {})


def open_case(shipment_id: str, requested_by: str, objective: str) -> dict:
    cases = _all()
    case_id = f"CASE-{len(cases) + 1:04d}"
    cases[case_id] = {
        "case_id": case_id,
        "shipment_id": shipment_id,
        "state": "investigating",
        "requested_by": requested_by,
        "requesters": [requested_by],  # everyone who has asked for an investigation
        "objective": objective,
        "opened": _now(),
        "finding": None,
        "finding_id": None,
        "flag": None,
        "events": [
            {
                "time": _now(),
                "to": "investigating",
                "by": requested_by,
                "detail": "investigation requested",
            }
        ],
    }
    storage.save("cases", cases)
    return cases[case_id]


def get(case_id: str) -> dict:
    return _all()[case_id]


def latest_for(shipment_id: str) -> dict | None:
    matching = [c for c in _all().values() if c["shipment_id"] == shipment_id]
    return matching[-1] if matching else None


def update(case_id: str, **fields) -> dict:
    cases = _all()
    cases[case_id].update(fields)
    storage.save("cases", cases)
    return cases[case_id]


def transition(
    case_id: str, to: str, by: str, detail: str, trace_id: str | None = None
) -> dict:
    """Move a case to a new state, if the lifecycle allows it, and record the move."""
    cases = _all()
    case = cases[case_id]
    authority = move(case["state"], to)  # raises IllegalTransition
    case["events"].append(
        {
            "time": _now(),
            "from": case["state"],
            "to": to,
            "by": by,
            "authority": authority,
            "detail": detail,
            "trace_id": trace_id,
        }
    )
    case["state"] = to
    storage.save("cases", cases)
    return case


def everything() -> dict:
    return _all()
