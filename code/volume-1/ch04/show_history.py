"""Chapter 4 demo: the history the framework built during a run, read back from the response."""

import asyncio
import sys

from investigate import agent

task = sys.argv[1] if len(sys.argv) > 1 else "Shipment SH-4471 is three days late. Find out why."
print(f"Task: {task}\n")
result = asyncio.run(agent.run(task))

for message in result.messages:
    for content in message.contents:
        if content.type == "text":
            print(f"Model says: {content.text.strip()}")
        elif content.type == "function_call":
            print(f"Model asks: {content.name}({content.arguments})")
        elif content.type == "function_result":
            print(f"Result:     {content.result}")

print(f"\n=== {len(result.messages)} messages, {result.usage_details['total_token_count']} tokens in total ===")
print(result.messages[-1].text)
