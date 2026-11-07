"""Chapter 12 contract tests: what each side of a boundary relies on, checked from the side that relies on it.

Two boundaries. The workflow's steps read Cobalt's systems through four functions in cobalt.py; the shapes
below are what the steps read, so the stand-ins must keep to them now, and a real adapter must later. The
model reads the instructions, the tool's schema and the case file; a snapshot fixes what it is sent, so any
change to it shows up as a failed test until someone accepts it with --snapshot-update.

    uv run pytest ch12/test_contracts.py -v
"""

import asyncio
import json
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from syrupy.extensions.json import JSONSnapshotExtension

import cobalt
from agentlab.llm import MODEL
from replies import SUPPORTED, report
from scripted import ScriptedClient
from steps import interpreter


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")  # ①


class ShipmentRecord(Strict):
    status: Literal["held", "in transit", "delivered"]  # LoadShipment compares it
    location: str
    contents: str
    due: str
    customs_case: str | None = Field(pattern=r"^RTM-\d{5}$")


class CaseRecord(Strict):
    shipment_id: str = Field(pattern=r"^SH-\d{4}$")
    status: Literal["on hold", "cleared"]
    # covered() compares it with DOCUMENT_HOLDS: a new reason must be added here
    hold_reason: (
        Literal["required document not received", "physical inspection"] | None
    )  # ②


class Filing(Strict):
    document_id: str = Field(pattern=r"^DOC-\d{4}$")
    uploaded: str
    filed_against_customs_case: str | None = Field(pattern=r"^RTM-\d{5}$")


class NotOnFile(Strict):
    found: Literal[False]
    message: str


class Failure(Strict):
    error: str  # every step tests for "error" to tell a failure from a record ③


class Required(Strict):
    document: str
    received: bool


SEARCH_RESULT = TypeAdapter(Filing | NotOnFile | Failure)


@pytest.mark.parametrize("shipment_id", cobalt.SHIPMENTS)
def test_shipment_records(shipment_id):
    ShipmentRecord.model_validate(cobalt.shipment_status(shipment_id))


@pytest.mark.parametrize("case_id", cobalt.CUSTOMS_CASES)
def test_case_records(case_id):  # ④
    CaseRecord.model_validate(cobalt.customs_case(case_id))


@pytest.mark.parametrize("case_id", cobalt.REQUIRED_DOCUMENTS)
def test_required_documents_and_every_search(case_id):
    shipment_id = cobalt.customs_case(case_id)["shipment_id"]
    for item in cobalt.required_documents(case_id):
        Required.model_validate(item)
        SEARCH_RESULT.validate_python(
            cobalt.document_search(shipment_id, item["document"])
        )


def test_failures_have_one_shape():
    Failure.model_validate(cobalt.shipment_status("SH-9999"))
    Failure.model_validate(cobalt.customs_case("RTM-00000"))
    cobalt.make_store_busy()
    Failure.model_validate(cobalt.document_search("SH-4471", "commercial invoice"))


@pytest.mark.parametrize(
    "read, key",
    [
        (lambda: cobalt.shipment_status("SH-4471"), "status"),
        (lambda: cobalt.customs_case("RTM-88213"), "status"),
        (lambda: cobalt.required_documents("RTM-88213")[0], "document"),
        (
            lambda: cobalt.document_search("SH-4471", "commercial invoice"),
            "document_id",
        ),
    ],
    ids=["shipment_status", "customs_case", "required_documents", "document_search"],
)
def test_reads_return_copies(read, key):
    before = read()[key]
    read()[key] = "changed by the test"
    assert read()[key] == before


@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)


def test_what_the_model_is_sent(build, snapshot_json):
    client = ScriptedClient([report(SUPPORTED)])
    asyncio.run(build(interpreter(client)).run("SH-4471"))
    [(messages, options)] = client.sent  # ①
    assert {
        "model": MODEL,
        "instructions": options["instructions"].splitlines(),  # diffs line by line
        "tools": [tool.to_json_schema_spec() for tool in options["tools"]],  # ②
        "messages": [
            {"role": m.role, "case file": json.loads(m.text)} for m in messages
        ],
    } == snapshot_json  # ③
