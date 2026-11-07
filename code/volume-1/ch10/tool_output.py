"""Chapter 10 demo: the finding as a tool call. The provider sees the Finding's schema as the tool's parameters.

The agent ends its investigation by calling report_finding, whose parameters are the Finding's fields. The
framework validates the arguments against the Pydantic model before the tool runs, and sends any failure back
to the model as the tool's result; the program reads the finding from the last valid call.
"""

import argparse
import asyncio

from agent_framework import FunctionTool

from cobalt import CUSTOMS_CASES, DOCUMENTS, SHIPMENTS, TOOLS
from contracts import Finding, provenance_problems, record_problems
from investigate import TASK, investigator

TOOL_INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight's operations team.

Goal: find the root cause of a delay and the action that would fix it.

How to work:
- Use the tools to check facts. Never guess a status, case number or document location.
- Before each tool call, say in one sentence what you want to find out.
- A hold or a delay is a symptom. Keep investigating until you find what caused it,
  or until no tool can tell you more.

Limits:
- You can only read Cobalt's systems. Recommend actions; never claim to have taken one.

Answer format: when you have finished, call report_finding once with your finding. \
Don't answer in text."""


def report(**finding) -> str:
    """Report the investigation's finding to Cobalt's case system."""
    return "Recorded."


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("task", nargs="?", default=TASK)
args = parser.parse_args()

report_finding = FunctionTool(name="report_finding", description=report.__doc__,
                              func=report, input_model=Finding)  # ①
agent = investigator(instructions=TOOL_INSTRUCTIONS, tools=[*TOOLS, report_finding])
result = asyncio.run(agent.run(args.task))

notes = [m.text for m in result.messages if m.role == "assistant" and m.text]
print(f"Notes before tool calls: {len(notes)}, of which blank: {sum(not n.strip() for n in notes)}")
calls = [c for m in result.messages for c in m.contents
         if c.type == "function_call" and c.name == "report_finding"]
results = {c.call_id: c.result for m in result.messages for c in m.contents
           if c.type == "function_result"}
accepted = [call for call in calls if results.get(call.call_id) == "Recorded."]
print(f"report_finding calls: {len(calls)}; results: {[results.get(call.call_id) for call in calls]}")
if not accepted:
    print(f"Final text:\n{result.messages[-1].text}\nOutcome: no finding reported")
else:
    finding = Finding.model_validate_json(accepted[-1].arguments)  # ②
    problems = provenance_problems(finding, result) + record_problems(
        finding, SHIPMENTS, CUSTOMS_CASES, DOCUMENTS)
    print(finding.model_dump_json(indent=2))
    for problem in problems:
        print(f"- {problem}")
    print(f"Outcome: reported; status {finding.status}{'; evidence problems' if problems else ''}; "
          f"{len(calls)} call(s)")
