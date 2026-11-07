"""The refiling gate and the lifecycle it drives, with no model: a case concluded with a checked
finding, then every way a refiling request can be refused, decided, filed, lost and recovered."""

from datetime import UTC, datetime, timedelta

import pytest

from cobalt_exceptions.domain.approval import RefilingRequest, decision_refusal
from cobalt_exceptions.domain.contracts import Finding, Flagged, InvestigationRequest
from cobalt_exceptions.services import casework, gate
from cobalt_exceptions.systems import approvals, cases, records
from findings import misfiled_invoice

TRACE = "4471a" + "0" * 27


def proposed_case() -> dict:
    """SH-4471's case after an investigation whose finding passed the workflow's checks."""
    case = casework.begin(
        InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-017")
    )
    return casework.conclude(
        case["case_id"], Finding.model_validate(misfiled_invoice()), TRACE
    )


def request_from_elsewhere(case: dict, **changes) -> RefilingRequest:
    """A request another caller sends to the gate: an analyst's tool, or another agent."""
    now = datetime.now(UTC)
    fields = dict(
        request_id=approvals.next_id(),
        case_id=case["case_id"],
        shipment_id="SH-4471",
        finding_id=TRACE,
        document_id="DOC-5531",
        customs_case="RTM-88213",
        expected_version=1,
        requested_by="analyst-022",
        created=now.isoformat(),
        expires=(now + timedelta(hours=1)).isoformat(),
    )
    return RefilingRequest(**fields | changes)


def test_the_finding_becomes_a_pending_request():
    case = proposed_case()
    [request] = approvals.everything()
    assert (case["state"], request.status) == ("proposed", "pending")
    assert (request.document_id, request.customs_case, request.finding_id) == (
        "DOC-5531",
        "RTM-88213",
        TRACE,
    )


def test_a_request_that_doesnt_match_the_finding_is_refused_before_anyone_is_asked():
    case = proposed_case()
    refused = gate.submit(request_from_elsewhere(case, document_id="DOC-5530"))
    assert refused.status == "refused"
    assert refused.reason == "document_id is DOC-5530, but the finding says DOC-5531"
    assert [r.request_id for r in gate.pending()] == ["REQ-0001"]


def test_a_request_for_a_flagged_case_is_refused():
    case = casework.begin(
        InvestigationRequest(shipment_id="SH-4588", requested_by="analyst-017")
    )
    case = casework.conclude(case["case_id"], None, TRACE, error="TimeoutError")
    refused = gate.submit(
        request_from_elsewhere(
            case,
            shipment_id="SH-4588",
            document_id="DOC-5802",
            customs_case="RTM-88377",
        )
    )
    assert refused.reason == "the case has no accepted finding that names a refiling"


def test_a_second_request_while_one_waits_is_refused():
    case = proposed_case()
    refused = gate.submit(request_from_elsewhere(case))
    assert refused.reason == "CASE-0001 is proposed, not waiting for a refiling"


def test_a_request_after_a_rejection_is_refused():
    case = proposed_case()
    gate.decide("REQ-0001", "lead-031", approve=False)
    refused = gate.submit(request_from_elsewhere(case))
    assert refused.reason == "CASE-0001 is with_person, not waiting for a refiling"


def test_a_flag_replaces_the_earlier_finding():
    case = proposed_case()
    gate.decide("REQ-0001", "lead-031", approve=False)
    casework.begin(InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-017"))
    flagged = Flagged(shipment_id="SH-4471", reason="no_usable_finding", finding=None, problems=["x"])
    casework.conclude(case["case_id"], flagged, "4471b" + "0" * 27)
    refused = gate.submit(request_from_elsewhere(case, finding_id="4471b" + "0" * 27))
    assert refused.reason == "the case has no accepted finding that names a refiling"


def test_the_requester_comes_from_the_case_not_the_request():
    case = casework.begin(InvestigationRequest(shipment_id="SH-4471", requested_by="lead-044"))
    casework.conclude(case["case_id"], Finding.model_validate(misfiled_invoice()), TRACE)
    approvals.put(approvals.get("REQ-0001").model_copy(update={"requested_by": "someone-else"}))
    with pytest.raises(PermissionError, match="lead-044 asked for this investigation"):
        gate.decide("REQ-0001", "lead-044", approve=True)


def test_only_approvers_can_approve():
    case = proposed_case()
    with pytest.raises(
        PermissionError,
        match="only approvers may approve refilings, and analyst-022 isn't one",
    ):
        gate.decide("REQ-0001", "analyst-022", approve=True)
    assert approvals.get("REQ-0001").status == "pending"
    assert cases.get(case["case_id"])["state"] == "proposed"


def test_a_non_approver_is_refused_for_the_role_before_the_request_status():
    proposed_case()
    gate.decide("REQ-0001", "lead-031", approve=False)
    with pytest.raises(PermissionError, match="analyst-022 isn't one"):
        gate.decide("REQ-0001", "analyst-022", approve=True)


def test_the_policy_itself_refuses_a_non_approver():
    proposed_case()
    reason = decision_refusal(
        approvals.get("REQ-0001"), "analyst-022", [], gate.APPROVERS, datetime.now(UTC)
    )
    assert reason == "analyst-022 may not approve refilings"


def test_an_approver_who_asked_for_an_earlier_investigation_cant_approve_a_later_one():
    case = casework.begin(InvestigationRequest(shipment_id="SH-4471", requested_by="lead-044"))
    casework.conclude(case["case_id"], Finding.model_validate(misfiled_invoice()), TRACE)
    gate.decide("REQ-0001", "lead-031", approve=False)
    casework.begin(InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-022"))
    casework.conclude(case["case_id"], Finding.model_validate(misfiled_invoice()), TRACE)
    with pytest.raises(PermissionError, match="lead-044 asked for"):
        gate.decide("REQ-0002", "lead-044", approve=True)


def test_an_approver_who_asked_for_the_investigation_cant_approve_its_refiling():
    case = casework.begin(
        InvestigationRequest(shipment_id="SH-4471", requested_by="lead-044")
    )
    casework.conclude(
        case["case_id"], Finding.model_validate(misfiled_invoice()), TRACE
    )
    with pytest.raises(
        PermissionError,
        match="lead-044 asked for this investigation and can't approve its refiling",
    ):
        gate.decide("REQ-0001", "lead-044", approve=True)


def test_an_unanswered_request_expires_and_the_case_goes_to_a_person():
    case = proposed_case()
    later = datetime.now(UTC) + timedelta(hours=25)
    assert gate.expire_due(later) == ["REQ-0001"]
    with pytest.raises(PermissionError, match="not pending"):
        gate.decide("REQ-0001", "lead-031", approve=True)
    assert cases.get(case["case_id"])["state"] == "with_person"


def test_a_rejection_files_nothing():
    case = proposed_case()
    gate.decide("REQ-0001", "lead-031", approve=False)
    assert cases.get(case["case_id"])["state"] == "with_person"
    assert records.load_records()["filings"] == []


def test_an_approval_files_once_and_the_case_waits_for_customs():
    case = proposed_case()
    request = gate.decide("REQ-0001", "lead-031", approve=True)
    assert (request.status, request.outcome["filing"]) == ("filed", "FIL-001")
    assert (
        casework.check_release(case["case_id"])["state"] == "filed"
    )  # filed is not released
    assert records.customs_processes() == ["RTM-88213"]
    assert casework.check_release(case["case_id"])["state"] == "closed"


def test_a_filing_customs_never_clears_goes_to_a_person():
    case = proposed_case()
    gate.decide("REQ-0001", "lead-031", approve=True)
    later = datetime.now(UTC) + timedelta(days=4)
    assert casework.check_release(case["case_id"], later)["state"] == "with_person"


def test_any_failed_filing_call_leaves_the_outcome_unknown(monkeypatch):
    case = proposed_case()

    def times_out(*args, **kwargs):
        raise TimeoutError("no answer")

    monkeypatch.setattr(gate.filing, "refile", times_out)
    assert gate.decide("REQ-0001", "lead-031", approve=True).status == "unknown"
    assert cases.get(case["case_id"])["state"] == "outcome_unknown"


def test_recovery_sends_again_when_the_store_has_nothing_under_the_key(monkeypatch):
    case = proposed_case()

    def never_arrives(*args, **kwargs):
        raise TimeoutError("no answer")

    with monkeypatch.context() as patch:
        patch.setattr(gate.filing, "refile", never_arrives)
        gate.decide("REQ-0001", "lead-031", approve=True)
    assert records.load_records()["filings"] == []
    assert gate.recover("REQ-0001").status == "filed"
    assert len(records.load_records()["filings"]) == 1
    assert cases.get(case["case_id"])["state"] == "filed"


def test_a_document_changed_since_the_finding_is_not_filed():
    case = proposed_case()
    records.colleague_replaces("DOC-5531")
    request = gate.decide("REQ-0001", "lead-031", approve=True)
    assert request.status == "not_filed"
    assert request.outcome["error"] == "conflict"
    assert cases.get(case["case_id"])["state"] == "with_person"


def test_a_refiling_the_store_refused_isnt_recovered():
    proposed_case()
    records.colleague_replaces("DOC-5531")
    assert gate.decide("REQ-0001", "lead-031", approve=True).status == "not_filed"
    with pytest.raises(ValueError, match="not_filed; there is nothing to recover"):
        gate.recover("REQ-0001")
    assert records.load_records()["filings"] == []


def test_one_lost_reply_is_retried_under_the_same_key():
    proposed_case()
    records.drop_replies(1)
    assert gate.decide("REQ-0001", "lead-031", approve=True).status == "filed"
    assert len(records.load_records()["filings"]) == 1


def test_a_reply_lost_every_time_leaves_the_outcome_unknown_until_recovered():
    case = proposed_case()
    records.drop_replies(3)
    assert gate.decide("REQ-0001", "lead-031", approve=True).status == "unknown"
    assert cases.get(case["case_id"])["state"] == "outcome_unknown"
    assert gate.recover("REQ-0001").status == "filed"
    assert len(records.load_records()["filings"]) == 1
    assert cases.get(case["case_id"])["state"] == "filed"


def test_a_case_with_an_action_in_flight_isnt_investigated_again():
    proposed_case()
    with pytest.raises(casework.CaseBusy, match="proposed"):
        casework.begin(
            InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-022")
        )


def test_a_cause_without_a_refiling_goes_to_a_person():
    case = casework.begin(
        InvestigationRequest(shipment_id="SH-4502", requested_by="analyst-017")
    )
    finding = misfiled_invoice(
        shipment_id="SH-4502",
        fault={"document": "packing list", "problem": "not_uploaded"},
        refiling=None,
        recommended_action="Obtain the packing list and file it against RTM-88301.",
    )
    case = casework.conclude(case["case_id"], Finding.model_validate(finding), TRACE)
    assert case["state"] == "with_person" and approvals.everything() == []


def test_every_move_records_its_authority_and_trace():
    case = proposed_case()
    gate.decide("REQ-0001", "lead-031", approve=True)
    moves = [
        (e.get("from"), e["to"], e["by"])
        for e in cases.get(case["case_id"])["events"]
    ]
    assert moves == [
        (None, "investigating", "analyst-017"),
        ("investigating", "proposed", "gate"),
        ("proposed", "approved", "lead-031"),
        ("approved", "action_attempted", "gate"),
        ("action_attempted", "filed", "document store"),
    ]
    assert {e["trace_id"] for e in cases.get(case["case_id"])["events"][1:]} == {
        TRACE
    }


def test_whoever_asked_for_a_later_investigation_cant_approve_its_refiling():
    case = proposed_case()
    gate.decide("REQ-0001", "lead-031", approve=False)
    casework.begin(InvestigationRequest(shipment_id="SH-4471", requested_by="lead-044"))
    casework.conclude(case["case_id"], Finding.model_validate(misfiled_invoice()), TRACE)
    with pytest.raises(PermissionError, match="lead-044 asked for this investigation"):
        gate.decide("REQ-0002", "lead-044", approve=True)


def test_a_request_during_a_second_investigation_is_refused():
    case = proposed_case()
    gate.decide("REQ-0001", "lead-031", approve=False)
    casework.begin(InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-022"))
    refused = gate.submit(request_from_elsewhere(case))
    assert refused.reason == "the case has no accepted finding that names a refiling"
