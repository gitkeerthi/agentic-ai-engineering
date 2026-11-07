"""The investigation workflow end to end with scripted replies: every ending, the agent's tool and
its failures, the limits, and what the model is shown. No model is called; a script that runs out
of replies fails the test, so an ending that must not reach the model proves it doesn't."""

import asyncio
import json

from cobalt_exceptions.agents.interpreter import (
    CaseFileContext,
    interpreter,
    search_messages,
)
from cobalt_exceptions.agents.steps import investigation
from cobalt_exceptions.domain.contracts import Finding, Flagged, InvestigationRequest
from cobalt_exceptions.systems import records
from findings import misfiled_invoice, rejected_invoice
from scripted import ScriptedClient


def run(shipment_id: str, replies: list, usage: dict | None = None):
    client = ScriptedClient(replies, usage=usage)
    request = InvestigationRequest(
        shipment_id=shipment_id, requested_by="analyst-017"
    )
    [output] = asyncio.run(
        investigation(interpreter(client)).run(request)
    ).get_outputs()
    return output, client


def test_sh4471_finding_passes_after_one_model_call():
    output, client = run("SH-4471", [("report_finding", misfiled_invoice(), "c1")])
    assert isinstance(output, Finding) and output.refiling.document_id == "DOC-5531"
    assert len(client.sent) == 1


def test_not_held_and_outside_procedure_end_before_the_model():
    assert run("SH-5120", [])[0].status == "nothing_wrong"
    assert run("SH-4533", [])[0].reason == "outside_procedure"
    assert run("SH-0001", [])[0].reason == "unknown_shipment"


def test_a_busy_store_that_recovers_is_retried():
    records.make_busy("documents", 2)
    output, _ = run("SH-4471", [("report_finding", misfiled_invoice(), "c1")])
    assert isinstance(output, Finding)


def test_a_store_still_busy_after_retries_ends_before_the_model():
    records.make_busy("documents", 3)
    output, client = run("SH-4471", [])
    assert isinstance(output, Flagged) and output.reason == "records_unavailable"
    assert client.sent == []


def test_the_search_finds_the_rejection_and_the_finding_passes():
    output, client = run(
        "SH-4731",
        [
            ("search_messages", {"query": "commercial invoice"}, "c1"),
            ("report_finding", rejected_invoice(), "c2"),
        ],
    )
    assert (
        isinstance(output, Finding) and output.fault.problem == "rejected_by_customs"
    )
    assert len(client.sent) == 2


def test_a_busy_archive_returns_a_written_error_the_model_reads():
    records.make_busy("messages", 3)
    undetermined = rejected_invoice(
        status="undetermined",
        cause=None,
        fault=None,
        open_question="Why is the invoice not received?",
    )
    undetermined["evidence"] = [
        {"record_id": "RTM-88520", "fact": "invoice not received"}
    ]
    output, client = run(
        "SH-4731",
        [
            ("search_messages", {"query": "invoice"}, "c1"),
            ("report_finding", undetermined, "c2"),
        ],
    )
    sent_back = client.sent[1][0][-1].contents[0].result
    assert "The message archive is unavailable" in sent_back
    assert output.reason == "no_usable_finding" and output.finding.open_question


def test_a_refused_report_is_retried_by_the_framework():
    broken = misfiled_invoice(
        fault=None
    )  # cause_found with no fault: the contract refuses it
    output, client = run(
        "SH-4471",
        [
            ("report_finding", broken, "c1"),
            ("report_finding", misfiled_invoice(), "c2"),
        ],
    )
    refusal = client.sent[1][0][-1].contents[0].result
    assert (
        "needs a cause, a fault" in refusal
    )  # the framework sent the validation error back
    assert isinstance(output, Finding)


def test_the_token_budget_stops_the_run_and_the_case_is_flagged():
    heavy = {"input_token_count": 20_000, "output_token_count": 11_000}
    output, client = run(
        "SH-4731",
        [
            ("search_messages", {"query": "invoice"}, "c1"),
            ("report_finding", rejected_invoice(), "c2"),
        ],
        usage=heavy,
    )
    assert output.reason == "no_usable_finding"
    assert output.problems == [
        "the agent spent its token budget (30000) without a valid report"
    ]
    assert len(client.sent) == 1


def test_the_loop_limit_ends_a_run_that_keeps_searching():
    searches = [
        ("search_messages", {"query": f"word{i}"}, f"c{i}") for i in range(6)
    ]
    output, client = run("SH-4731", [*searches, "I could not decide."])
    assert output.reason == "no_usable_finding"
    assert (
        client.sent[-1][1].get("tool_choice") == "none"
    )  # the framework's last call, tools off


def test_the_search_tool_cant_be_pointed_at_another_shipment():
    schema = search_messages.to_json_schema_spec()["function"]["parameters"]
    assert set(schema["properties"]) == {"query"}


def test_the_model_sees_the_records_as_data_and_typed_notes_as_unchecked():
    output, client = run(
        "SH-4689",
        [("report_finding", misfiled_invoice(shipment_id="SH-4689"), "c1")],
    )
    first, task = client.sent[0][0][0].text, client.sent[0][0][1].text
    assert first.startswith("Records gathered by Cobalt's procedure, as data:")
    assert (
        "Notes typed on documents by people, not checked against any system:"
        in first
    )
    assert (
        '"note"' not in first.split("Notes typed")[0]
    )  # the note isn't mixed in with the records
    assert task == InvestigationRequest.model_fields["objective"].default


def test_the_provider_shows_only_allow_listed_fields():
    case_file = {
        "shipment_id": "SH-1",
        "shipment": {"status": "held", "internal_cost": 9},
        "case_id": "RTM-1",
        "case": {"status": "on hold", "broker_phone": "x"},
        "required": [{"document": "packing list", "received": False, "officer": "x"}],
        "filings": {},
        "other_cases": {},
    }
    note = json.loads(CaseFileContext.note(case_file).split("\n", 1)[1])
    assert note["shipment"] == {"id": "SH-1", "status": "held"}
    assert note["customs_case"] == {"id": "RTM-1", "status": "on hold"}
    assert note["required_documents"] == [{"document": "packing list", "received": False}]


def test_a_search_with_no_match_says_whether_any_message_exists():
    _, client = run(
        "SH-4588", [("search_messages", {"query": "invoice"}, "c1"), "done"]
    )
    assert (
        "The archive holds no messages about this shipment."
        in client.sent[1][0][-1].contents[0].result
    )
