"""Chapter 5 demo: one run with each tool_choice setting. Must the model call a tool, may it, or may it not?

By default the question needs no lookup; --investigation asks Chapter 4's task instead, which does.
"""

import argparse
import asyncio

from cobalt import TOOLS
from investigate import TASK, investigator, show

QUESTION = "What does it mean when customs puts a shipment on hold?"
SETTINGS = {
    "auto": "auto",
    "required": "required",
    "named": {"mode": "required", "required_function_name": "get_shipment_status"},
    "none": "none",
}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("tool_choice", choices=SETTINGS, help="the run's tool_choice option")
parser.add_argument("--investigation", action="store_true", help="ask the investigation task instead of the general question")
args = parser.parse_args()
question = TASK if args.investigation else QUESTION

agent = investigator(TOOLS)
print(f"Question: {question}  (tool_choice: {SETTINGS[args.tool_choice]})\n")
result = asyncio.run(agent.run(question, options={"tool_choice": SETTINGS[args.tool_choice]}))
show(result)
print(f"\nModel calls: {sum(1 for m in result.messages if m.role == 'assistant')}.")
