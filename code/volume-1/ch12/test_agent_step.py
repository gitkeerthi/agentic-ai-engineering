"""Chapter 12 component tests: the interpreter agent on its own, with a scripted client in place of the model.

The component is everything our code and the framework do around the model's reply: the instructions and the
one tool it is offered, the framework's check of the arguments against Finding, the middleware that stops the
run after a report, and reported_finding(), which reads the result.

    uv run pytest ch12/test_agent_step.py -v
"""

import asyncio

import pytest

from replies import SUPPORTED, report
from scripted import ScriptedClient, UnexpectedModelCall
from steps import INSTRUCTIONS, interpreter, reported_finding

INVALID = {**SUPPORTED, "evidence": []}  # cause_found with no evidence


def run(replies: list):
    client = ScriptedClient(replies)
    result = asyncio.run(interpreter(client).run('{"shipment_id": "SH-4471"}'))
    return reported_finding(result), client.sent


def test_a_report_ends_the_run():
    finding, sent = run([report(SUPPORTED, "call_1")])
    assert finding.model_dump() == SUPPORTED
    assert len(sent) == 1  # no second model call after the report ①


def test_the_agent_is_offered_one_tool_and_its_instructions():
    _, sent = run([report(SUPPORTED, "call_1")])
    messages, options = sent[0]
    assert [tool.name for tool in options["tools"]] == ["report_finding"]
    assert options["instructions"] == INSTRUCTIONS
    assert [m.role for m in messages] == ["user"]  # the case file, and nothing else


def test_invalid_arguments_are_refused_and_the_model_told():
    finding, sent = run([report(INVALID, "call_1"), report(SUPPORTED, "call_2")])
    assert finding.model_dump() == SUPPORTED  # the second, valid report
    told = sent[1][0][-1].contents[0]
    assert (told.call_id, told.result) == (
        "call_1",
        "Error: Argument parsing failed.",
    )  # ②


def test_three_invalid_reports_end_with_no_finding():
    replies = [report(INVALID, f"call_{n}") for n in (1, 2, 3)] + ["Done."]
    finding, sent = run(replies)
    assert finding is None
    assert len(sent) == 4
    assert sent[-1][1]["tool_choice"] == "none"  # the last call has tools off ③


def test_an_answer_in_text_gives_no_finding():
    finding, sent = run(["The invoice was misfiled."])
    assert finding is None and len(sent) == 1


def test_a_call_the_script_didnt_allow_fails_loudly():
    with pytest.raises(UnexpectedModelCall, match="model call 1, but the script"):
        run([])
