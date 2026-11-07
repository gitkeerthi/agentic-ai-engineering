"""The refiling gate: the only part of the application that may file (the dependency rule enforces it).

propose() takes the refiling from a case's accepted finding; submit() checks any request, from
whoever sends it, against the case and that finding, and against the store's rules, before a person
is asked; decide() records a person's decision and, on approval, files with the request's ID as the
idempotency key; recover() settles a filing whose outcome is unknown; expire_due() closes requests
nobody answered. No model call sits between the finding and the filing.
"""

from datetime import UTC, datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

from ..domain.approval import RefilingRequest, decision_refusal, submission_refusal
from ..systems import approvals, cases, filing, records

APPROVERS = {"lead-031", "lead-044"}  # in production, a role in the identity provider
LIFETIME = timedelta(hours=24)
OPEN = {"pending", "approved", "unknown", "filed"}


def _now() -> datetime:
    return datetime.now(UTC)


def propose(case_id: str, now: datetime | None = None) -> RefilingRequest:
    """A refiling request built from the case's accepted finding, submitted like any other."""
    now = now or _now()
    case = cases.get(case_id)
    refiling = case["finding"]["refiling"]
    request = RefilingRequest(
        request_id=approvals.next_id(),
        case_id=case_id,
        shipment_id=case["shipment_id"],
        finding_id=case["finding_id"],
        document_id=refiling["document_id"],
        customs_case=refiling["customs_case"],
        expected_version=records.document(refiling["document_id"])["version"],
        requested_by=case["requesters"][-1],  # who asked for this investigation
        created=now.isoformat(timespec="seconds"),
        expires=(now + LIFETIME).isoformat(timespec="seconds"),
    )
    return submit(request, proposal=True)


def submit(request: RefilingRequest, proposal: bool = False) -> RefilingRequest:
    """Queue a request for a person, or refuse it now: it must match the case's accepted finding
    and come while the case is waiting for one (①), and pass the document store's own rules (②)."""
    case = cases.get(request.case_id)
    open_requests = [r for r in approvals.everything() if r.status in OPEN]
    reason = submission_refusal(request, case, open_requests)  # ①
    reason = reason or records.check_refile(request.document_id, request.customs_case)  # ②
    request.status, request.reason = ("refused", reason) if reason else ("pending", None)
    approvals.put(request)
    if proposal:  # the application's own proposal moves the case; another caller's never does
        to = "with_person" if reason else "proposed"
        detail = f"refiling refused: {reason}" if reason else f"{request.request_id} waits for approval"
        cases.transition(request.case_id, to, "gate", detail, request.finding_id)
    return request


def decide(
    request_id: str, approver: str, approve: bool, now: datetime | None = None
) -> RefilingRequest:
    """Record one person's decision; on approval, file the refiling and record what
    the store says. Each refusal names the rule it applies. The gate holds the
    approver set, so it checks the role first; the policy checks it again."""
    if approver not in APPROVERS:  # ① the role
        raise PermissionError(
            f"only approvers may approve refilings, and {approver} isn't one"
        )
    request = approvals.get(request_id)
    requesters = cases.get(request.case_id)["requesters"]  # ② from the case
    reason = decision_refusal(
        request, approver, requesters, APPROVERS, now or _now()
    )
    if reason:  # not pending, the approver asked for an investigation, or expired
        raise PermissionError(reason)
    decision = "approved" if approve else "with_person"
    detail = f"{request_id} {'approved' if approve else 'rejected'}"
    # ③ The case moves first: if the lifecycle refuses, nothing is recorded.
    cases.transition(request.case_id, decision, approver, detail, request.finding_id)
    request.decided_by = approver
    request.status = "approved" if approve else "rejected"
    approvals.put(request)
    return _file(request) if approve else request  # ④ filed under the request's ID


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.05, max=0.5), reraise=True)
def _refile(request: RefilingRequest) -> dict:
    # Safe to retry: the request's ID is the idempotency key, so the store files once at most.
    return filing.refile(
        request.document_id,
        request.customs_case,
        request.expected_version,
        key=request.request_id,
        approved_by=request.decided_by,
    )


def _send(request: RefilingRequest) -> RefilingRequest:
    """File, and settle the answer. Any failure that isn't an answer from the store leaves the
    outcome unknown: from the caller's side, a lost reply and a request that never arrived look alike."""
    try:
        answer = _refile(request)
    except Exception as error:
        request.status = "unknown"
        approvals.put(request)
        detail = f"no answer from the document store ({type(error).__name__})"
        cases.transition(request.case_id, "outcome_unknown", "gate", detail, request.finding_id)
        return request
    return _settle(request, answer)


def _file(request: RefilingRequest) -> RefilingRequest:
    detail = f"{request.request_id} sent to the document store"
    cases.transition(request.case_id, "action_attempted", "gate", detail, request.finding_id)
    return _send(request)


def _settle(request: RefilingRequest, answer: dict) -> RefilingRequest:
    request.outcome = answer
    if "error" in answer:  # the store refused, or the document changed since the request
        request.status = "not_filed"
        approvals.put(request)
        detail = f"not filed: {answer['message']}"
        cases.transition(request.case_id, "with_person", "document store", detail, request.finding_id)
        return request
    request.status = "filed"
    approvals.put(request)
    detail = f"{answer['filing']}: awaiting customs"
    cases.transition(request.case_id, "filed", "document store", detail, request.finding_id)
    return request


def recover(request_id: str) -> RefilingRequest:
    """Settle a filing whose outcome is unknown: ask the store under the key, and send again only
    if it has nothing."""
    request = approvals.get(request_id)
    if request.status != "unknown":
        raise ValueError(f"request {request_id} is {request.status}; there is nothing to recover")
    if stored := filing.outcome_of(request_id):
        return _settle(request, stored)
    detail = "nothing filed under the key: sending again"
    cases.transition(request.case_id, "action_attempted", "gate", detail, request.finding_id)
    return _send(request)


def expire_due(now: datetime | None = None) -> list[str]:
    """Close every pending request whose lifetime has passed. In production, a scheduled job runs this."""
    now = now or _now()
    expired = []
    for request in approvals.everything():
        if request.status == "pending" and now > datetime.fromisoformat(request.expires):
            request.status, request.reason = "expired", f"nobody answered by {request.expires}"
            approvals.put(request)
            detail = f"{request.request_id} expired"
            cases.transition(request.case_id, "with_person", "gate", detail, request.finding_id)
            expired.append(request.request_id)
    return expired


def pending() -> list[RefilingRequest]:
    return [r for r in approvals.everything() if r.status == "pending"]
