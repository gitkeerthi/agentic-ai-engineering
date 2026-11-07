"""Chapter 3 demo: the original ReAct loop, with actions written as plain text and parsed by the code.

Before tool calling existed, this was how agents worked. Compare it with loop.py, which uses tool calling.
"""

import json
import re
import sys

from agentlab.llm import chat
from cobalt import TOOLS

# The tools are described in plain text, because the model has no other way to learn about them.
INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight. You can use these tools:
- get_shipment_status(shipment_id): Look up one shipment's status, location, contents, due day and customs case ID (if any).
- get_customs_case(case_id): Look up a customs case: which shipment it belongs to, its status and why it is on hold.
- list_required_documents(case_id): List the documents a customs case requires and whether customs has received each one.
- find_document(shipment_id, document_type): Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against.

Work in steps. In each step write exactly two lines:
Thought: what you want to find out next, and why.
Action: tool_name {"argument": "value"}

Then stop. You will receive the result as a line starting with "Observation:".
When you know the cause, write instead:
Thought: why you are done.
Final Answer: the cause and the recommended action, in two sentences."""

ACTION = re.compile(r"^Action:\s*(\w+)\s*(\{.*\})\s*$", re.MULTILINE)

task = sys.argv[1] if len(sys.argv) > 1 else "Shipment SH-4471 is three days late. Find out why."
messages = [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": task}]
print(f"Task: {task}\n")

for _ in range(8):
    text = chat(messages, stop=["Observation:"]).choices[0].message.content.strip()
    print(text)
    messages.append({"role": "assistant", "content": text})

    if "Final Answer:" in text:
        break
    match = ACTION.search(text)
    if match is None:
        observation = 'No valid Action line found. Write: Action: tool_name {"argument": "value"}'
    elif match.group(1) not in TOOLS:
        observation = f"Unknown tool {match.group(1)}"
    else:
        try:
            observation = json.dumps(TOOLS[match.group(1)](**json.loads(match.group(2))))
        except (json.JSONDecodeError, TypeError) as exc:
            observation = f"Bad arguments: {exc}"
    print(f"Observation: {observation}\n")
    messages.append({"role": "user", "content": f"Observation: {observation}"})
