"""Chapter 11 demo: Cobalt's procedure for a delayed shipment, written into an agent's instructions.

The agent is Chapter 10's, reporting its finding with report_finding. The instructions add the procedure's five
steps, in order. The program prints the path the agent took (its tool calls, in order), what the run cost, and
the finding.

    uv run python ch11/procedure_agent.py [TASK] [--store-busy] [--trace]

--store-busy makes the document store answer every search with "busy". --trace prints the run's spans as a
tree when it ends.
"""

import argparse
import asyncio
import time

from agent_framework import Agent, FunctionTool, MiddlewareTermination, function_middleware
from agent_framework.observability import configure_otel_providers

from agentlab.llm import make_client
from agentlab.tracing import SpanTreePrinter
from agentlab.usage import mark, since
from cobalt import TOOLS, make_store_busy
from contracts import Finding

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

TASK = "Shipment SH-4471 is three days late. Find out why."


def report(**finding) -> str:
    """Report the investigation's finding to Cobalt's case system."""
    return "Recorded."


@function_middleware
async def stop_after_report(context, call_next) -> None:
    await call_next()
    if context.function.name == "report_finding":
        raise MiddlewareTermination("finding recorded", result=context.result)


parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("task", nargs="?", default=TASK)
parser.add_argument("--store-busy", action="store_true")
parser.add_argument("--trace", action="store_true")
args = parser.parse_args()
if args.store_busy:
    make_store_busy()
if args.trace:
    configure_otel_providers(exporters=[SpanTreePrinter()], enable_sensitive_data=False)

report_finding = FunctionTool(
    name="report_finding", description=report.__doc__, func=report, input_model=Finding
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

start, began = mark(), time.monotonic()
result = asyncio.run(agent.run(args.task))
seconds = time.monotonic() - began

calls = [c for m in result.messages for c in m.contents if c.type == "function_call"]
path = [
    f"{c.name}({', '.join(str(v) for v in c.parse_arguments().values())})"
    for c in calls
    if c.name != "report_finding"
]
print("Path:")
for step, call in enumerate(path, 1):
    print(f"  {step}. {call}")
reports = [c for c in calls if c.name == "report_finding"]
finding = Finding.model_validate_json(reports[-1].arguments) if reports else None
if finding:
    print(f"\nFinding: {finding.model_dump_json(indent=2)}")
else:
    print(f"\nNo finding reported. The run's last message:\n{result.messages[-1].text}")
print(f"\nCost: {since(start)}; seconds: {seconds:.1f}")
print(
    f"Outcome: {finding.status if finding else 'no finding'}; path: {' > '.join(c.name for c in calls if c.name != 'report_finding')}"
)
