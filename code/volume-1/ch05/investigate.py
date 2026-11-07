"""Chapter 4's investigation agent, built for whichever tools (and instructions) a program gives it, and a printer for its runs."""

from agent_framework import Agent, AgentResponse

from agentlab.llm import make_client

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

TASK = "Shipment SH-4471 is three days late. Find out why."


def investigator(tools: list, instructions: str = INSTRUCTIONS) -> Agent:
    client = make_client()
    client.function_invocation_configuration["max_iterations"] = 10
    return Agent(client, instructions, name="investigator", tools=tools)


def show(result: AgentResponse) -> None:
    """Print each tool call and what the model received, then the answer."""
    for message in result.messages[:-1]:
        for content in message.contents:
            if content.type == "function_call":
                print(f"Model asks: {content.name}({content.arguments})")
            elif content.type == "function_result":
                print(f"Result:     {content.result}")
                if content.exception:
                    print(f"            (kept by the program, not sent: {content.exception})")
    print(f"\n{result.messages[-1].text}")
