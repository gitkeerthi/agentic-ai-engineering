"""Chapter 13 demo: evaluate an agent that chooses its own tools, with Microsoft Agent Framework's
evaluate_agent() and expected tool calls.

    uv run python ch13/tool_choice.py [REPEATS]

The agent is Chapter 11's procedure agent: the procedure is in its instructions, and it chooses each lookup
itself. For every case in the golden set, the calls the procedure requires are worked out from the records.
evaluate_agent() runs the agent on each case REPEATS times (default 3) and scores each run with two of the
framework's checks and two of ours. Prints each check's passes per case, and the reason for every failure.
"""

import asyncio
import sys

from agent_framework import (
    Agent,
    CheckResult,
    ExpectedToolCall,
    FunctionTool,
    LocalEvaluator,
    MiddlewareTermination,
    evaluate_agent,
    evaluator,
    function_middleware,
    tool_call_args_match,
    tool_calls_present,
)

from agentlab.llm import make_client
from agentlab.usage import mark, since
from cobalt import DOCUMENTS, REQUIRED_DOCUMENTS, SHIPMENTS, TOOLS
from contracts import Finding
from golden import CASES

INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight's operations team.

Follow Cobalt's procedure for a delayed shipment, every time, in this order:
1. Look up the shipment.
2. If it has a customs case, look up the case.
3. List the documents the case requires.
4. Search the document store for every required document, including the ones customs has received,
   and note the customs case each one is filed against.
5. For any document filed against a different customs case, look up that case too.
Then call report_finding once with your finding. Don't answer in text.

Limits:
- You can only read Cobalt's systems. Recommend actions; never claim to have taken one."""


def report(**finding) -> str:
    """Report the investigation's finding to Cobalt's case system."""
    return "Recorded."


@function_middleware
async def stop_after_report(context, call_next) -> None:
    await call_next()
    if context.function.name == "report_finding":
        raise MiddlewareTermination("finding recorded", result=context.result)


def procedure(shipment_id: str) -> list[ExpectedToolCall]:
    """The calls Cobalt's procedure requires for this shipment, in order, worked out from the records."""
    calls = [ExpectedToolCall("get_shipment_status", {"shipment_id": shipment_id})]
    case_id = SHIPMENTS[shipment_id]["customs_case"]
    if case_id is None:
        return calls
    calls += [
        ExpectedToolCall("get_customs_case", {"case_id": case_id}),
        ExpectedToolCall("list_required_documents", {"case_id": case_id}),
    ]
    others = []
    for item in REQUIRED_DOCUMENTS[case_id]:
        kind = item["document"]
        calls.append(
            ExpectedToolCall(
                "find_document", {"shipment_id": shipment_id, "document_type": kind}
            )
        )
        filed = DOCUMENTS.get((shipment_id, kind), {}).get(
            "filed_against_customs_case"
        )
        if filed not in (None, case_id):
            others.append(ExpectedToolCall("get_customs_case", {"case_id": filed}))
    return calls + others


def lookups(conversation) -> list[tuple[str, dict]]:
    """The lookups the agent made, in order, with string arguments lowercased."""
    return [
        (c.name, {k: str(v).lower() for k, v in c.parse_arguments().items()})
        for m in conversation
        for c in m.contents
        if c.type == "function_call" and c.name != "report_finding"
    ]


def matches(call: tuple[str, dict], want: ExpectedToolCall) -> bool:
    name, args = call
    return name == want.name and all(
        args.get(k) == str(v).lower() for k, v in want.arguments.items()
    )


@evaluator
def in_procedure_order(conversation: list, expected_tool_calls: list) -> bool:
    """Every required call was made, in the procedure's order. Argument case is ignored."""
    made = iter(lookups(conversation))
    return all(
        any(matches(call, want) for call in made) for want in expected_tool_calls
    )


@evaluator
def nothing_beyond_procedure(
    conversation: list, expected_tool_calls: list
) -> CheckResult:
    """No lookup the procedure doesn't require. The reason names any extra ones."""
    extra = lookups(conversation)
    for want in expected_tool_calls:
        found = next((call for call in extra if matches(call, want)), None)
        if found:
            extra.remove(found)
    described = [f"{name}({', '.join(args.values())})" for name, args in extra]
    return CheckResult(
        passed=not extra,
        reason=f"extra lookups: {described}" if extra else "none",
        check_name="nothing_beyond_procedure",
    )


repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 3
report_finding = FunctionTool(
    name="report_finding",
    description=report.__doc__,
    func=report,
    input_model=Finding,
)
client = make_client()
client.function_invocation_configuration["max_iterations"] = 9
agent = Agent(
    client,
    INSTRUCTIONS,
    name="investigator",
    tools=[*TOOLS, report_finding],
    middleware=[stop_after_report],
)
queries = [
    f"Shipment {case['shipment_id']} is late. Find out why." for case in CASES
]
expected = [procedure(case["shipment_id"]) for case in CASES]
checks = LocalEvaluator(
    tool_calls_present,
    tool_call_args_match,
    in_procedure_order,
    nothing_beyond_procedure,
)


async def main() -> None:
    start = mark()
    [results] = await evaluate_agent(
        agent=agent,
        queries=queries,
        expected_tool_calls=expected,
        num_repetitions=repeats,
        evaluators=checks,
    )  # ①
    names = list(results.per_evaluator)
    print(f"{'Case':<10}{'calls':>6}  " + "  ".join(f"{n:>24}" for n in names))
    failures = []
    for index, case in enumerate(CASES):
        items = results.items[
            index :: len(CASES)
        ]  # this case's runs, one per repetition
        passes = {n: 0 for n in names}
        for item in items:
            for score in item.scores:
                passes[score.name] += score.passed
                if not score.passed:
                    failures.append(
                        (case["shipment_id"], score.name, score.sample["reason"])
                    )
        row = "  ".join(f"{passes[n]:>21}/{len(items)}" for n in names)
        print(f"{case['shipment_id']:<10}{len(expected[index]):>6}  {row}")
    totals = {n: results.per_evaluator[n] for n in names}
    print(
        "\nTotals: "
        + "; ".join(
            f"{n} {t['passed']}/{t['passed'] + t['failed']}"
            for n, t in totals.items()
        )
    )
    print("\nEvery failure:")
    for shipment_id, name, reason in failures:
        print(f"  {shipment_id} {name}: {reason}")
    print(f"\nCost: {since(start)}")


asyncio.run(main())
