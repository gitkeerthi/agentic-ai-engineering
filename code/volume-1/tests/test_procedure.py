"""The procedure's rules, called directly: the endings each read decides, and the checks a finding
must pass, including the typed fault and where each piece of evidence came from."""

from cobalt_exceptions.domain.contracts import Finding, Flagged
from cobalt_exceptions.domain.procedure import (
    after_case,
    after_shipment,
    check_finding,
)
from cobalt_exceptions.systems import messages, records
from findings import case_file, misfiled_invoice, rejected_invoice, undetermined


def test_a_shipment_with_no_customs_case_and_not_held_has_nothing_wrong():
    ending = after_shipment("SH-5120", records.shipment_status("SH-5120"))
    assert isinstance(ending, Finding) and ending.status == "nothing_wrong"


def test_an_unknown_shipment_is_flagged():
    ending = after_shipment("SH-0001", records.shipment_status("SH-0001"))
    assert isinstance(ending, Flagged) and ending.reason == "unknown_shipment"


def test_an_inspection_hold_is_outside_the_procedure():
    shipment = records.shipment_status("SH-4533")
    case = records.customs_case("RTM-88350")
    ending = after_case(
        "SH-4533",
        shipment,
        "RTM-88350",
        case,
        records.required_documents("RTM-88350"),
    )
    assert ending.reason == "outside_procedure"


def test_the_misfiled_invoice_passes():
    finding = Finding.model_validate(misfiled_invoice())
    assert check_finding(finding, case_file("SH-4471"), {}) == finding


def test_a_refiling_must_be_the_one_the_fault_needs():
    wrong = misfiled_invoice(
        refiling={"document_id": "DOC-5530", "customs_case": "RTM-88213"}
    )
    flagged = check_finding(Finding.model_validate(wrong), case_file("SH-4471"), {})
    assert flagged.reason == "finding_problems"
    assert "the fix is to refile DOC-5531 against RTM-88213" in flagged.problems


def test_a_rejection_needs_the_customs_message_it_cites():
    finding = Finding.model_validate(rejected_invoice())
    retrieved = {"MSG-7104": messages.message("MSG-7104")}
    assert check_finding(finding, case_file("SH-4731"), retrieved) == finding


def test_a_message_the_agent_never_retrieved_cant_be_cited():
    flagged = check_finding(
        Finding.model_validate(rejected_invoice()), case_file("SH-4731"), {}
    )
    assert (
        "MSG-7104 is cited but isn't in the case file or the messages retrieved"
        in flagged.problems
    )
    assert any("no customs rejection" in p for p in flagged.problems)


def test_a_disguised_abstention_is_flagged():
    """Chapter 13's released wrong finding: cause_found on records that don't show a cause."""
    disguised = rejected_invoice(
        shipment_id="SH-4588",
        cause="The records do not identify which document is outstanding.",
        fault={"document": "commercial invoice", "problem": "not_uploaded"},
        evidence=[
            {"record_id": "RTM-88377", "fact": "on hold for a document not received"}
        ],
    )
    flagged = check_finding(
        Finding.model_validate(disguised), case_file("SH-4588"), {}
    )
    assert flagged.reason == "finding_problems"
    assert (
        "customs has received the commercial invoice, so it isn't what holds the shipment"
        in flagged.problems
    )


def test_not_uploaded_is_checked_against_the_store():
    claim = misfiled_invoice(
        fault={"document": "commercial invoice", "problem": "not_uploaded"},
        refiling=None,
    )
    flagged = check_finding(Finding.model_validate(claim), case_file("SH-4471"), {})
    assert "the store has the commercial invoice as DOC-5531" in flagged.problems


def test_undetermined_goes_to_a_person_with_its_question():
    flagged = check_finding(
        Finding.model_validate(undetermined("SH-4588", "RTM-88377")),
        case_file("SH-4588"),
        {},
    )
    assert flagged.reason == "no_usable_finding"
    assert flagged.finding.open_question == "What is customs still waiting for?"


def test_no_report_is_flagged_with_the_reason():
    flagged = check_finding(
        None, case_file("SH-4471"), {}, note="the agent reported no valid finding"
    )
    assert (flagged.reason, flagged.problems) == (
        "no_usable_finding",
        ["the agent reported no valid finding"],
    )
