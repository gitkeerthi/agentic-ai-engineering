"""Chapter 5 demo: an agent built with no tools, given tools run by run. What do the definitions cost on a call?"""

import argparse
import asyncio

from cobalt import TOOLS
from investigate import investigator, show

QUESTION = "What does it mean when customs puts a shipment on hold?"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("offer", choices=["all", "none"], help="offer the four tools for this run, or none")
offer = parser.parse_args().offer

agent = investigator([])  # built with no tools
tools = TOOLS if offer == "all" else []
print(f"Question: {QUESTION}  (tools offered: {', '.join(t.name for t in tools) or 'none'})\n")
result = asyncio.run(agent.run(QUESTION, tools=tools))
show(result)
model_calls = sum(1 for m in result.messages if m.role == "assistant")
print(f"\nModel calls: {model_calls}. Input tokens: {result.usage_details['input_token_count']}.")
