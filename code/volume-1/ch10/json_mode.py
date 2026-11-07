"""Chapter 10 demo: the same investigation, answered as one JSON object and checked by the program.

The request asks for JSON mode (any valid JSON object); the instructions carry the Finding's JSON Schema,
generated from the Pydantic model. The program then makes the four checks on the reply: JSON, contract, business records, provenance.
--prompt-only asks for the JSON in the instructions alone, without JSON mode.
"""

import argparse
import asyncio

from cobalt import CUSTOMS_CASES, DOCUMENTS, SHIPMENTS
from contracts import check, provenance_problems, record_problems
from investigate import JSON_INSTRUCTIONS, TASK, investigator

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("task", nargs="?", default=TASK)
parser.add_argument("--prompt-only", action="store_true")
args = parser.parse_args()

agent = investigator(instructions=JSON_INSTRUCTIONS)
options = {} if args.prompt_only else {"response_format": {"type": "json_object"}}
result = asyncio.run(agent.run(args.task, options=options))  # ①
reply = result.messages[-1].text  # the final reply; result.text would join the notes before each tool call too
notes = [m.text for m in result.messages[:-1] if m.role == "assistant" and m.text]
print(f"Notes before tool calls: {len(notes)}, of which blank: {sum(not n.strip() for n in notes)}")
print(f"Reply:\n{reply}\n")

finding, verdict = check(reply)  # ②
problems = provenance_problems(finding, result) + record_problems(
    finding, SHIPMENTS, CUSTOMS_CASES, DOCUMENTS) if finding else []
print(f"Check: {verdict}")
for problem in problems:
    print(f"- {problem}")
if finding:
    print(f"status={finding.status} refiling={finding.refiling.model_dump() if finding.refiling else None}")
print(f"Outcome: {verdict}{'; evidence problems' if problems else ''}"
      f"{'; status ' + finding.status if finding else ''}")
