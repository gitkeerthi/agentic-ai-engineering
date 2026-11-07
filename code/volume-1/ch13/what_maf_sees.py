"""Chapter 13 demo, no model: what Microsoft Agent Framework's evaluation functions see of the investigation.

    uv run python ch13/what_maf_sees.py

The agent's replies are scripted, so every run is the same and free. Four probes: evaluate_workflow() on the
whole investigation; evaluate_agent() on the interpreter agent, with a keyword check that its finding passes; a
check that returns a graded score of 0.7; and the framework's argument check on a document search whose type
differs from the expected one only in its capital letter.
"""

import asyncio
import json

from agent_framework import (
    Agent,
    ExpectedToolCall,
    LocalEvaluator,
    evaluate_agent,
    evaluate_workflow,
    evaluator,
    keyword_check,
    tool_call_args_match,
)

from cobalt import find_document
from scripted import ScriptedClient
from steps import interpreter, investigation

SUPPORTED = {
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


def scripted_agent():
    return interpreter(ScriptedClient([("report_finding", SUPPORTED, "call_1")]))


@evaluator
def what_it_sees(response: str, conversation: list) -> bool:
    print(f"  response text: {response!r}")
    print(
        f"  conversation: {[(m.role, [c.type for c in m.contents]) for m in conversation]}"
    )
    return True


@evaluator
def graded(response: str) -> float:
    return 0.7


async def main() -> None:
    print("1. evaluate_workflow() on the investigation")
    [result] = await evaluate_workflow(
        workflow=investigation(scripted_agent()),
        queries=["SH-4471"],
        evaluators=LocalEvaluator(keyword_check("DOC-5531")),
    )
    [item] = result.items
    print(f"  per-agent results: {list(result.sub_results) or 'none'}")
    print(f"  overall item's response text: {item.output_text[:72]}...")
    print(f"  keyword_check('DOC-5531'): {item.status}")

    print("\n2. evaluate_agent() on the interpreter agent")
    case_file = json.dumps(
        {"shipment_id": "SH-4471"}
    )  # the reply is scripted, so any message will do
    [result] = await evaluate_agent(
        agent=scripted_agent(),
        queries=[case_file],
        evaluators=LocalEvaluator(keyword_check("DOC-5531"), what_it_sees),
    )
    print(f"  keyword_check('DOC-5531'): {result.per_evaluator['keyword_check']}")
    print(f"  reason: {result.error}")

    print("\n3. A check that returns a graded score of 0.7")
    [result] = await evaluate_agent(
        agent=scripted_agent(),
        queries=[case_file],
        evaluators=LocalEvaluator(graded),
    )
    [score] = result.items[0].scores
    print(
        f"  score: {score.score}; passed: {score.passed}; reason: {score.sample['reason']}"
    )

    print(
        "\n4. tool_call_args_match on find_document(SH-4471, 'Commercial invoice')"
    )
    search = {"shipment_id": "SH-4471", "document_type": "Commercial invoice"}
    searcher = Agent(
        ScriptedClient([("find_document", search, "call_1"), "Done."]),
        tools=[find_document],
    )
    [result] = await evaluate_agent(
        agent=searcher,
        queries=["Find SH-4471's commercial invoice."],
        expected_tool_calls=[
            ExpectedToolCall(
                "find_document",
                {"shipment_id": "SH-4471", "document_type": "commercial invoice"},
            )
        ],
        evaluators=LocalEvaluator(tool_call_args_match),
    )
    [score] = result.items[0].scores
    print(f"  passed: {score.passed}; reason: {score.sample['reason']}")


asyncio.run(main())
