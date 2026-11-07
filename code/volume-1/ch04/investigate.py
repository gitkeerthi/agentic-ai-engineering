"""Chapter 4 demo: Chapter 3's investigation agent, rebuilt with Microsoft
Agent Framework."""

import argparse
import asyncio

from agent_framework import Agent

from agentlab.llm import make_client
from cobalt import TOOLS

INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight's operations team.

Goal: find the root cause of a delay and the action that would fix it.

How to work:
- Use the tools to check facts. Never guess a status, case number or document location.
- Before each tool call, say in one sentence what you want to find out.
- A hold or a delay is a symptom. Keep investigating until you find what caused it,
  or until no tool can tell you more.

Limits:
- You can only read Cobalt's systems. Recommend actions; never claim to have taken one.

Answer format:
Cause: one sentence.
Evidence: the facts that show it, with IDs.
Recommended action: one sentence."""

client = make_client()
# 9 rounds of tool calls, then one more call: 10 calls at most; the default is 40
client.function_invocation_configuration["max_iterations"] = 9
agent = Agent(client, INSTRUCTIONS, name="investigator", tools=TOOLS)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "task", nargs="?",
        default="Shipment SH-4471 is three days late. Find out why.",
    )
    args = parser.parse_args()
    print(f"Task: {args.task}\n")
    result = asyncio.run(agent.run(args.task))
    print(result.text)
