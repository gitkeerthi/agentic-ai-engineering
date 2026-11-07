"""The approval policy for a refiling: which requests a person may be asked about, and who may answer.

A refiling request is only ever taken from a finding the workflow has checked. Whoever submits one
(the application itself, an analyst's tool, another agent in a later chapter), the gate compares it
with the case's accepted finding and refuses it if they differ, before anyone is asked.
"""

from datetime import datetime

from pydantic import BaseModel

from .contracts import Finding


class RefilingRequest(BaseModel):
    request_id: str
    case_id: str
    shipment_id: str
    finding_id: str  # the trace ID of the investigation whose finding it comes from
    document_id: str
    customs_case: str
    expected_version: int  # the document's version when the request was made
    requested_by: str
    created: str
    expires: str
    status: str = "pending"  # pending, refused, rejected, expired, approved, filed, not_filed, unknown
    reason: str | None = None
    decided_by: str | None = None
    outcome: dict | None = None


def mismatch(request: RefilingRequest, finding: Finding | None) -> list[str]:
    """How the request differs from the refiling the accepted finding names."""
    if finding is None or finding.refiling is None:
        return ["the case has no accepted finding that names a refiling"]
    wanted = {
        "shipment_id": finding.shipment_id,
        "document_id": finding.refiling.document_id,
        "customs_case": finding.refiling.customs_case,
    }
    return [
        f"{name} is {getattr(request, name)}, but the finding says {value}"
        for name, value in wanted.items()
        if getattr(request, name) != value
    ]


def submission_refusal(
    request: RefilingRequest,
    case: dict,
    open_requests: list[RefilingRequest],
) -> str | None:
    """Why the gate won't put this request in front of a person, or None if it may."""
    finding = Finding.model_validate(case["finding"]) if case["finding"] else None
    if problems := mismatch(request, finding):
        return "; ".join(problems)
    if request.finding_id != case["finding_id"]:
        return (
            f"the request cites finding {request.finding_id}, "
            f"not the case's accepted finding {case['finding_id']}"
        )
    if case["state"] != "investigating":  # only a just-checked finding is proposed
        return f"{case['case_id']} is {case['state']}, not waiting for a refiling"
    for other in open_requests:  # one open action per document: no second filing
        if (
            other.document_id == request.document_id
            and other.request_id != request.request_id
        ):
            return (
                f"{other.request_id} already covers "
                f"{request.document_id} ({other.status})"
            )
    return None


def decision_refusal(
    request: RefilingRequest,
    approver: str,
    requesters: list[str],
    approvers: set[str],
    now: datetime,
) -> str | None:
    """Why this person can't answer this request now, or None if they can.
    requesters are everyone who asked for an investigation of the case, as the case
    records them, never a value the request carries."""
    if request.status != "pending":
        return f"request {request.request_id} is not pending ({request.status})"
    if approver not in approvers:
        return f"{approver} may not approve refilings"
    if approver in requesters:  # separation of duties
        return f"{approver} asked for this investigation and can't approve its refiling"
    if now > datetime.fromisoformat(request.expires):
        return f"request {request.request_id} expired at {request.expires}"
    return None
