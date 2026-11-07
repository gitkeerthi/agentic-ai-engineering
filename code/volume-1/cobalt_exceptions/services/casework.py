"""The case lifecycle as the application runs it: open a case for a request, record how the
investigation ended, hand a refiling to the gate, and close the case when customs releases it.
"""

from datetime import UTC, datetime, timedelta

from ..domain.contracts import Finding, Flagged, InvestigationRequest
from ..domain.lifecycle import OPEN_ACTION
from ..systems import cases, records
from . import gate


RELEASE_WAIT = timedelta(days=3)  # how long a filed case waits for customs before a person looks


class CaseBusy(Exception):
    """The shipment's case has an action in flight; investigating again could propose it twice."""


def begin(request: InvestigationRequest) -> dict:
    """The case this investigation belongs to: a new one, or one a person handed back."""
    case = cases.latest_for(request.shipment_id)
    if case and case["state"] in OPEN_ACTION | {"investigating"}:
        raise CaseBusy(
            f"{case['case_id']} for {request.shipment_id} is {case['state']}"
        )
    if case and case["state"] == "with_person":
        # A new run starts with no accepted finding, and its requester joins the case's.
        cases.update(
            case["case_id"],
            finding=None,
            finding_id=None,
            flag=None,
            requesters=[*case["requesters"], request.requested_by],
        )
        return cases.transition(
            case["case_id"],
            "investigating",
            request.requested_by,
            "investigate again",
        )
    return cases.open_case(
        request.shipment_id, request.requested_by, request.objective
    )


def conclude(
    case_id: str, output: Finding | Flagged | None, trace_id: str, error: str = ""
) -> dict:
    """Record the investigation's ending on the case, and move the case on."""
    if output is None:
        cases.update(case_id, finding=None, flag=None, finding_id=trace_id)
        return cases.transition(
            case_id,
            "with_person",
            "workflow",
            f"the investigation failed: {error}",
            trace_id,
        )
    if isinstance(output, Flagged):
        # A flag replaces any earlier finding: only a finding this run accepted may be acted on.
        cases.update(case_id, finding=None, flag=output.model_dump(), finding_id=trace_id)
        detail = f"flagged ({output.reason}): {'; '.join(output.problems)}"
        return cases.transition(case_id, "with_person", "workflow", detail, trace_id)
    cases.update(case_id, finding=output.model_dump(), flag=None, finding_id=trace_id)
    if output.status == "nothing_wrong":
        return cases.transition(
            case_id, "closed", "workflow", "nothing holds the shipment", trace_id
        )
    if output.refiling is None:
        detail = f"for a person: {output.recommended_action}"
        return cases.transition(case_id, "with_person", "workflow", detail, trace_id)
    gate.propose(case_id)
    return cases.get(case_id)


def check_release(case_id: str, now: datetime | None = None) -> dict:
    """Close a filed case once customs has cleared it; a filing alone doesn't release a shipment.
    A filed case customs hasn't cleared within the release wait goes to a person."""
    case = cases.get(case_id)
    if case["state"] != "filed":
        return case
    customs_case = case["finding"]["refiling"]["customs_case"]
    if records.customs_case(customs_case)["status"] == "cleared":
        detail = f"{customs_case} cleared"
        return cases.transition(case_id, "closed", "customs", detail, case["finding_id"])
    filed_at = datetime.fromisoformat(case["events"][-1]["time"])
    if (now or datetime.now(UTC)) - filed_at > RELEASE_WAIT:
        detail = f"{customs_case} still on hold {RELEASE_WAIT.days} days after the filing"
        return cases.transition(case_id, "with_person", "release check", detail, case["finding_id"])
    return case
