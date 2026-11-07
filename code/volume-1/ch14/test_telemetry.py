"""What every run must leave behind, checked without a model: the agent replies from a script.

uv run pytest ch14
"""

import asyncio
import json

import cobalt
from opentelemetry import trace
import telemetry
from scripted import ScriptedClient
from show import load, spans_of
from steps import interpreter, investigation

FINDING = {
    "shipment_id": "SH-4471",
    "status": "cause_found",
    "cause": "The commercial invoice is filed against customs case RTM-88124 instead of RTM-88213.",
    "evidence": [{"record_id": "DOC-5531", "fact": "Filed against RTM-88124."}],
    "recommended_action": "Refile DOC-5531 against RTM-88213.",
    "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"},
}


def observed_run(replies: list, shipment_id: str = "SH-4471"):
    """One observed investigation with a scripted agent; returns the case record, the agent and its spans."""
    agent = interpreter(
        client=ScriptedClient(replies), middleware=[telemetry.keep_evidence]
    )
    record = asyncio.run(
        telemetry.investigate(investigation(agent), agent, shipment_id)
    )
    telemetry.flush()
    return record, agent


def test_root_span_carries_the_configuration(store):
    record, agent = observed_run([("report_finding", FINDING, "call_1")])
    [root] = [
        s for s in spans_of(store, record["trace_id"]) if s["name"] == "investigate"
    ]
    assert {
        k: root["attributes"][k] for k in telemetry.configuration(agent)
    } == telemetry.configuration(agent)
    assert root["resource"]["attributes"]["service.version"] == telemetry.RELEASE


def test_the_case_record_finds_the_model_and_tool_calls(store):
    record, _ = observed_run([("report_finding", FINDING, "call_1")])
    operations = [
        s["attributes"].get("gen_ai.operation.name")
        for s in spans_of(store, record["trace_id"])
    ]
    assert record["outcome"] == "finding"
    assert {"invoke_agent", "chat", "execute_tool"} <= set(operations)


def test_the_evidence_is_kept_under_the_same_trace_id(store):
    record, _ = observed_run([("report_finding", FINDING, "call_1")])
    [evidence] = [
        e for e in load(store, "evidence") if e["trace_id"] == record["trace_id"]
    ]
    assert "Rotterdam customs yard" in evidence["sent"]


def test_no_case_file_or_finding_text_reaches_the_trace(store):
    record, _ = observed_run([("report_finding", FINDING, "call_1")])
    spans = json.dumps(spans_of(store, record["trace_id"]))
    logs = json.dumps(
        [
            r
            for r in load(store, "logs")
            if r["trace_id"] == "0x" + record["trace_id"]
        ]
    )
    for text in (
        "Rotterdam customs yard",
        "industrial pumps",
        "instead of RTM-88213",
        "You interpret",
    ):
        assert text not in spans and text not in logs


def test_a_failed_run_still_leaves_a_trace_and_a_record(store):
    cobalt.make_store_busy()
    record, _ = observed_run([])  # the run fails before the agent: no model call
    spans = spans_of(store, record["trace_id"])
    [root] = [s for s in spans if s["name"] == "investigate"]
    assert record["outcome"] == "failed" and record["output"] is None
    assert root["status"]["status_code"] == "ERROR"
    assert root["attributes"]["error.type"] == "StoreUnavailable"
    assert any(
        s["name"] == "read document_search"
        and s["status"]["status_code"] == "ERROR"
        for s in spans
    )


def test_a_flagged_run_logs_a_line_with_its_trace_id(store):
    nothing_wrong = {
        **FINDING,
        "status": "nothing_wrong",
        "cause": None,
        "refiling": None,
    }
    record, _ = observed_run([("report_finding", nothing_wrong, "call_1")])
    lines = [
        r for r in load(store, "logs") if r["trace_id"] == "0x" + record["trace_id"]
    ]
    assert record["outcome"] == "flagged"
    assert [r["body"] for r in lines] == [
        "SH-4471 flagged for review: no_usable_finding"
    ]


def test_evidence_is_kept_when_the_model_call_fails(store):
    record, _ = observed_run([ConnectionError("provider unreachable")])
    [evidence] = [e for e in load(store, "evidence") if e["trace_id"] == record["trace_id"]]
    assert record["outcome"] == "failed"
    assert "Rotterdam customs yard" in evidence["sent"] and evidence["response"] is None


def test_without_tracing_each_run_still_gets_its_own_id():
    with trace.use_span(trace.INVALID_SPAN):  # what every span is with no provider
        first, second = telemetry.correlation_id(), telemetry.correlation_id()
    assert first != second and first != "0" * 32


def test_a_read_that_raises_records_its_class_not_its_message(store):
    def lookup(record_id):
        raise TimeoutError("customer Hartmann Pumpen GmbH: no reply")

    with trace.get_tracer("test").start_as_current_span("request") as parent:
        try:
            telemetry.read(lookup, "SH-4471")
        except TimeoutError:
            pass
    telemetry.flush()
    trace_id = format(parent.get_span_context().trace_id, "032x")
    [span] = [s for s in spans_of(store, trace_id) if s["name"] == "read lookup"]
    assert span["status"]["status_code"] == "ERROR"
    assert span["attributes"]["error.type"] == "TimeoutError"
    assert "Hartmann" not in json.dumps(span)
