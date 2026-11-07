"""Chapter 10's investigation agent: Chapter 8's, which reads Cobalt's systems and answers in a fixed text format."""

import json

from agent_framework import Agent, AgentResponse

from agentlab.llm import make_client
from cobalt import TOOLS
from contracts import Finding

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

# The same agent, answering with one JSON object. The schema is generated from the Pydantic model, so the
# instructions and the check agree on fields, types and patterns; the cross-field rules are written in both.
JSON_INSTRUCTIONS = f"""\
You investigate delayed shipments for Cobalt Freight's operations team.

Goal: find the root cause of a delay and the action that would fix it.

How to work:
- Use the tools to check facts. Never guess a status, case number or document location.
- Before each tool call, say in one sentence what you want to find out.
- A hold or a delay is a symptom. Keep investigating until you find what caused it,
  or until no tool can tell you more.

Limits:
- You can only read Cobalt's systems. Recommend actions; never claim to have taken one.

Answer format: reply with one JSON object and nothing else. It must match this JSON Schema:
{json.dumps(Finding.model_json_schema())}"""

TASK = "Shipment SH-4471 is three days late. Find out why."


def investigator(instructions: str = INSTRUCTIONS, tools=TOOLS, **settings) -> Agent:
    client = make_client()
    client.function_invocation_configuration["max_iterations"] = 9
    return Agent(client, instructions, name="investigator", tools=tools, **settings)


def show(result: AgentResponse) -> None:
    """Print each tool call, then the last message's text."""
    for message in result.messages:
        for content in message.contents:
            if content.type == "function_call":
                print(f"Model asks: {content.name}({content.arguments})")
    print(f"\n{result.messages[-1].text}")
