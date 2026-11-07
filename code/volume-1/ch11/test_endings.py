"""Chapter 11 test: every way the investigation workflow can end, each run once and checked.

No model call: the agent step's client replies from a script. Run it with pytest:

    uv run pytest ch11/test_endings.py -v
"""

import asyncio

import pytest

import cobalt
from scripted import ScriptedClient
from contracts import Finding
from steps import Flagged, StoreUnavailable, interpreter, investigation

GOOD = {
    "shipment_id": "SH-4471",
    "status": "cause_found",
    "cause": "The commercial invoice is filed against customs case RTM-88124 instead of RTM-88213.",
    "evidence": [
        {"record_id": "DOC-5531", "fact": "Filed against RTM-88124."},
        {
            "record_id": "RTM-88213",
            "fact": "On hold: required document not received.",
        },
    ],
    "recommended_action": "Refile DOC-5531 against RTM-88213.",
    "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"},
}
UNSEEN = {
    **GOOD,
    "evidence": [*GOOD["evidence"], {"record_id": "SH-0042", "fact": "Similar."}],
}
WRONG_CASE = {
    **GOOD,
    "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88124"},
}
NO_CAUSE = {**GOOD, "cause": None, "refiling": None, "recommended_action": None}
UNDETERMINED = {**NO_CAUSE, "status": "undetermined"}
NOTHING_WRONG = {**NO_CAUSE, "status": "nothing_wrong"}


def report(finding: dict) -> tuple:
    return ("report_finding", finding, "call_1")


def no_customs_case():
    cobalt.SHIPMENTS["SH-4471"]["customs_case"] = None


def no_case():
    cobalt.CUSTOMS_CASES.pop("RTM-88213")


def no_document_list():
    cobalt.REQUIRED_DOCUMENTS.pop("RTM-88213")


def no_other_case():
    cobalt.CUSTOMS_CASES.pop("RTM-88124")


def inspection():
    cobalt.CUSTOMS_CASES["RTM-88213"]["hold_reason"] = "physical inspection"


def case_cleared():
    cobalt.CUSTOMS_CASES["RTM-88213"]["status"] = "cleared"
    cobalt.CUSTOMS_CASES["RTM-88213"]["hold_reason"] = None


def delivered():
    cobalt.SHIPMENTS["SH-4471"]["status"] = "delivered"
    cobalt.CUSTOMS_CASES["RTM-88213"]["status"] = "cleared"


ENDINGS = {
    # name: (shipment, change to the records, agent replies, expected)
    # expected: a Finding's status, or a Flagged reason and a problem's phrase
    "supported finding":
        ("SH-4471", None, [report(GOOD)], "cause_found"),
    "nothing wrong, by Cobalt's rule":
        ("SH-5120", None, [], "nothing_wrong"),
    "nothing holding a delivered shipment":
        ("SH-4471", delivered, [], "nothing_wrong"),
    "evidence from outside the case file":
        ("SH-4471", None, [report(UNSEEN)], ("finding_problems", "SH-0042")),
    "refiling against the wrong case":
        ("SH-4471", None, [report(WRONG_CASE)], ("finding_problems", "RTM-88124")),
    "agent couldn't tell":
        ("SH-4471", None, [report(UNDETERMINED)], ("no_usable_finding", "couldn't")),
    "agent says nothing is wrong":
        ("SH-4471", None, [report(NOTHING_WRONG)], ("no_usable_finding", "on hold")),
    "answer in text":
        ("SH-4471", None, ["It was misfiled."], ("no_usable_finding", "no valid")),
    "unknown shipment":
        ("SH-9999", None, [], ("unknown_shipment", "No shipment found")),
    "held, with no customs case":
        ("SH-4471", no_customs_case, [], ("outside_procedure", "outside")),
    "customs hold for another reason":
        ("SH-4471", inspection, [], ("outside_procedure", "inspection")),
    "held, with the customs case cleared":
        ("SH-4471", case_cleared, [], ("outside_procedure", "cleared")),
    "customs case not on file":
        ("SH-4471", no_case, [], ("records_missing", "No customs case")),
    "no list of required documents":
        ("SH-4471", no_document_list, [], ("records_missing", "no list")),
    "document filed against a case not on file":
        ("SH-4471", no_other_case, [], ("records_missing", "aren't on file")),
}  # fmt: skip


@pytest.fixture(autouse=True)
def records():
    cobalt.reset()
    yield
    cobalt.reset()


def run(shipment_id: str, replies: list):
    # An empty script fails the test if the model is called.
    agent = interpreter(ScriptedClient(replies))
    return asyncio.run(investigation(agent).run(shipment_id)).get_outputs()


@pytest.mark.parametrize("name", ENDINGS)
def test_each_ending_gives_one_output(name):
    shipment_id, change, replies, expected = ENDINGS[name]
    if change:
        change()
    [output] = run(shipment_id, replies)  # exactly one output
    if isinstance(expected, str):
        assert isinstance(output, Finding) and output.status == expected
    else:
        reason, phrase = expected
        assert isinstance(output, Flagged) and output.reason == reason
        assert any(phrase in problem for problem in output.problems)


def test_store_busy_raises():
    cobalt.make_store_busy()
    with pytest.raises(StoreUnavailable):
        run("SH-4471", [])


def test_model_error_raises():
    with pytest.raises(ConnectionError):
        run("SH-4471", [ConnectionError("model endpoint unreachable")])
