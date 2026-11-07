"""What an investigation leaves behind: a run record with the trace ID, all seven configuration parts,
usage and cost; spans with IDs but no content; and the evidence, kept apart."""

import asyncio
import json

import pytest
from opentelemetry import trace

from cobalt_exceptions.agents import telemetry
from cobalt_exceptions.agents.interpreter import interpreter
from cobalt_exceptions.agents.steps import investigation
from cobalt_exceptions.domain.contracts import InvestigationRequest
from findings import misfiled_invoice
from scripted import ScriptedClient


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    path = telemetry.setup(tmp_path_factory.mktemp("telemetry"))
    yield path
    telemetry.close()


def test_a_run_leaves_a_joined_record(store):
    client = ScriptedClient(
        [("report_finding", misfiled_invoice(), "c1")],
        usage={"input_token_count": 4000, "output_token_count": 300},
    )
    agent = interpreter(client, middleware=[telemetry.keep_evidence])
    request = InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-017")
    run = asyncio.run(telemetry.investigate(investigation(agent), agent, request))
    assert len(run["trace_id"]) == 32 and run["outcome"] == "finding"
    assert set(run["configuration"]) == {
        "cobalt.release",
        "cobalt.instructions.md5",
        "cobalt.tools.md5",
        "cobalt.model",
        "cobalt.request_settings.md5",
        "cobalt.framework.version",
        "cobalt.code.md5",
    }
    assert run["usage"]["input_token_count"] == 4000
    trace.get_tracer_provider().force_flush()
    spans = [
        json.loads(line) for line in (store / "spans.jsonl").read_text().splitlines()
    ]
    mine = [s for s in spans if s["context"]["trace_id"] == "0x" + run["trace_id"]]
    names = {s["name"] for s in mine}
    assert {"investigate", "read shipment_status", "read document_search"} <= names
    text = json.dumps(mine)
    assert (
        misfiled_invoice()["cause"] not in text
    )  # sensitive data off: no content in the trace
    evidence = [
        json.loads(line)
        for line in (store / "evidence.jsonl").read_text().splitlines()
    ]
    assert any(
        e["trace_id"] == run["trace_id"] and "DOC-5531" in json.dumps(e["case_file"])
        for e in evidence
    )
