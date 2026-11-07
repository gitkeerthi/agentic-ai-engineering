"""Chapter 10 demo: what the framework does with a structured answer, tested with a scripted client. No model call.

1. report_finding called with arguments that fail the Finding: what the model is sent back, without and with
   include_detailed_errors, and whether the tool ran
2. the same with arguments that pass the schema but break the Finding's own rule (parts_agree)
3. three failing calls in a row
4. JSON mode: which of the loop's model calls carry the response format
5. response_format set to the Finding: what result.value does with a sentence before the JSON, and without it
6. valid findings that cite records no tool confirmed: SH-0042 (the first object in a real reply, json_mode.py
   --prompt-only, run 2 of 10 on SH-5120), and RTM-51200, which a lookup reported missing; then SH-0042 again,
   reported through report_finding, whose own result must not count as confirming it
7. function middleware that ends the run once report_finding has recorded a finding: how many model calls
"""

import asyncio
import json
import logging

from agent_framework import Agent, FunctionTool, MiddlewareTermination, function_middleware, tool

from contracts import Finding, check, provenance_problems
from scripted import ScriptedClient

logging.getLogger("agent_framework").setLevel(logging.ERROR)
ran = []


def report(**finding) -> str:
    ran.append(finding["status"])
    return "Recorded."


report_finding = FunctionTool(name="report_finding", description="Report the finding.", func=report, input_model=Finding)


@tool
def get_shipment_status(shipment_id: str) -> dict:
    """Look up a shipment."""
    return {"status": "in transit", "customs_case": None}


@tool
def get_customs_case(case_id: str) -> dict:
    """Look up a customs case."""
    return {"error": f"No customs case found with ID {case_id}"}


@function_middleware
async def stop_after_report(context, call_next) -> None:
    await call_next()
    if context.function.name == "report_finding":
        raise MiddlewareTermination("finding recorded", result=context.result)  # ①


VALID = {"shipment_id": "SH-4471", "status": "cause_found", "cause": "The invoice was filed against RTM-88124.",
         "evidence": [{"record_id": "DOC-5531", "fact": "The invoice is filed against RTM-88124."}],
         "recommended_action": "Refile DOC-5531 against RTM-88213.",
         "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"}}
BAD_STATUS = {**VALID, "status": "found"}
BREAKS_RULE = {**VALID, "status": "nothing_wrong", "cause": None}
PLACEHOLDER = {"shipment_id": "SH-5120", "status": "undetermined", "cause": None,
               "evidence": [{"record_id": "SH-0042", "fact": "Invalid placeholder - see note"}],
               "recommended_action": None, "refiling": None}


def tool_results(client: ScriptedClient) -> list[str]:
    """Every tool result the model was sent, in order, from the last call's messages."""
    messages, _ = client.sent[-1]
    return [str(c.result) for m in messages for c in m.contents if c.type == "function_result"]


async def answer(replies: list, detailed: bool = False, middleware=None, **options):
    client = ScriptedClient(replies)
    client.function_invocation_configuration["include_detailed_errors"] = detailed
    agent = Agent(client, "Investigate.", tools=[get_shipment_status, get_customs_case, report_finding],
                  middleware=middleware)
    result = await agent.run("SH-4471 is late.", options=options)
    return client, result


async def main() -> None:
    print("1. Arguments that fail the Finding, then valid ones")
    for detailed in (False, True):
        ran.clear()
        client, _ = await answer([("report_finding", BAD_STATUS, "c1"), ("report_finding", VALID, "c2"), "Done."], detailed)
        print(f"   include_detailed_errors={detailed}: model calls: {len(client.sent)}; tool ran for {ran}; "
              "the model was sent:")
        for result in tool_results(client):
            print(f"      {result.replace(chr(10), ' ')[:230]}")

    print("2. Arguments that break the Finding's rule (nothing_wrong with a refiling)")
    ran.clear()
    client, _ = await answer([("report_finding", BREAKS_RULE, "c1"), "Done."], detailed=True)
    print(f"   tool ran for {ran}; the model was sent: {tool_results(client)[0].replace(chr(10), ' ')[:230]}")

    print("3. Three failing calls in a row")
    ran.clear()
    client, result = await answer([("report_finding", BAD_STATUS, f"c{n}") for n in (1, 2, 3)] + ["Done."])
    print(f"   model calls: {len(client.sent)}; tool_choice on the last: {client.sent[-1][1].get('tool_choice')}; "
          f"tool ran for {ran}; final text: {result.messages[-1].text!r}")

    print("4. JSON mode: the response format on each model call")
    client, _ = await answer([("get_shipment_status", {"shipment_id": "SH-4471"}, "c1"), ("report_finding", VALID, "c2"),
                              json.dumps(VALID)], response_format={"type": "json_object"})
    for n, (_, options) in enumerate(client.sent, 1):
        print(f"   call {n}: response_format={options.get('response_format')}")

    print("5. response_format=Finding, and result.value")
    for label, reply in (("a sentence, then the JSON", "Here is the finding.\n\n" + json.dumps(VALID)),
                         ("the JSON alone", json.dumps(VALID))):
        _, result = await answer([reply], response_format=Finding)
        try:
            value = result.value
            print(f"   {label}: result.value is a {type(value).__name__}, status {value.status}")
        except Exception as error:
            print(f"   {label}: result.value raised {type(error).__name__}: {str(error).splitlines()[0][:160]}")

    print("6. Valid findings that cite records no tool confirmed")
    lookups = [("get_shipment_status", {"shipment_id": "SH-5120"}, "c1"),
               ("get_customs_case", {"case_id": "RTM-51200"}, "c2")]
    guessed_case = {**PLACEHOLDER, "evidence": [{"record_id": "RTM-51200", "fact": "No such case exists."}]}
    for reply in (PLACEHOLDER, guessed_case):
        _, result = await answer([*lookups, json.dumps(reply)])
        finding, verdict = check(result.messages[-1].text)
        print(f"   check: {verdict}; provenance: {provenance_problems(finding, result)}")
    _, result = await answer([*lookups, ("report_finding", PLACEHOLDER, "c3"), "Done."])
    print(f"   through report_finding: provenance: {provenance_problems(Finding(**PLACEHOLDER), result)}")

    print("7. Ending the run once report_finding has recorded a finding")
    for middleware in (None, [stop_after_report]):
        ran.clear()
        client, result = await answer([("report_finding", VALID, "c1"), "Done."], middleware=middleware)
        print(f"   {'with' if middleware else 'without'} the middleware: model calls: {len(client.sent)}; "
              f"tool ran for {ran}; last message: {result.messages[-1].role}")


asyncio.run(main())
