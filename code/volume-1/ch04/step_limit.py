"""Chapter 4 demo: what the framework returns when a run reaches its limit on rounds of tool calls, and how to notice."""

import asyncio
import sys

from investigate import agent

LIMIT = 2
agent.client.function_invocation_configuration["max_iterations"] = LIMIT

task = sys.argv[1] if len(sys.argv) > 1 else "Shipment SH-4471 is three days late. Find out why."
print(f"Task: {task}\n")
result = asyncio.run(agent.run(task))
print(result.messages[-1].text)

# Count the model's replies that asked for tools. If every allowed round did, the framework made one more call with tools off.
tool_rounds = 0
for message in result.messages:
    if any(content.type == "function_call" for content in message.contents):
        tool_rounds += 1
print(f"\nStop reason: {result.finish_reason}. "
      f"Rounds of tool calls: {tool_rounds} of {LIMIT} allowed.")
if tool_rounds == LIMIT:
    print("The run reached its limit, so the reply above is "
          "unfinished work, not an answer.")
