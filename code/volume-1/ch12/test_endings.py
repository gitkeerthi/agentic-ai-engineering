"""Chapter 12 workflow tests: every way the investigation can end, each run once and checked.

Chapter 11's table of endings, now run against the `build` fixture (conftest.py), so the same tests can check
the workflow with the_change.py's edit. No model call: the agent step's client replies from a script.

    uv run pytest ch12/test_endings.py -v
    uv run pytest ch12/test_endings.py -v --with-change
"""

import asyncio

import pytest
from agent_framework.exceptions import ChatClientException

import cobalt
from contracts import Finding
from replies import BUSY_STORE_FINDING, SUPPORTED as GOOD, report
from scripted import ScriptedClient
from steps import Flagged, StoreUnavailable, interpreter

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


def run(build, shipment_id: str, client: ScriptedClient):
    # An empty script fails the test if the model is called.
    workflow = build(interpreter(client))
    return asyncio.run(workflow.run(shipment_id)).get_outputs()


@pytest.mark.parametrize("name", ENDINGS)
def test_each_ending_gives_one_output(build, name):
    shipment_id, change, replies, expected = ENDINGS[name]
    if change:
        change()
    [output] = run(build, shipment_id, ScriptedClient(replies))  # exactly one output
    if isinstance(expected, str):
        assert isinstance(output, Finding) and output.status == expected
    else:
        reason, phrase = expected
        assert isinstance(output, Flagged) and output.reason == reason
        assert any(phrase in problem for problem in output.problems)


def test_no_finding_from_failed_searches(build):
    # Regression: the_change.py let this reply through as a finding.
    cobalt.make_store_busy()
    client = ScriptedClient([report(BUSY_STORE_FINDING)])  # ①
    try:
        [output] = run(build, "SH-4471", client)
    except StoreUnavailable:  # Chapter 11's design: stop before the agent step ②
        assert client.sent == []  # and without paying for a model call
        return
    # Any design may stop or flag the case; none may return a finding. ③
    assert not isinstance(output, Finding), "a finding from failed searches"


def test_model_error_raises(build):
    # The real chat client wraps every failure in ChatClientException.
    client = ScriptedClient([ChatClientException("model endpoint unreachable")])
    with pytest.raises(ChatClientException):
        run(build, "SH-4471", client)
