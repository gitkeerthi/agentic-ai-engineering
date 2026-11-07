"""Chapter 6's investigation agent, the questions its programs ask, and a meter that records each model call."""

from agent_framework import Agent, AgentResponse, ChatContext, chat_middleware

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

FIRST_TASK = "Shipment SH-4471 is three days late. Find out why."
FOLLOW_UP = "Which customs case was the invoice filed against, and what should the team change?"
SECOND_TASK = "Shipment SH-5120 is due next Wednesday. Check whether anything could delay it."
GO_BACK = "Go back to the first shipment you investigated. Which customs case was its invoice filed against?"

calls: list[dict] = []  # one entry per model call, filled by meter()


@chat_middleware
async def meter(context: ChatContext, call_next) -> None:
    """Record what each model call sent and what the provider counted."""
    await call_next()
    usage = context.result.usage_details or {}
    calls.append({
        "messages": len(context.messages),
        "input": usage.get("input_token_count", 0),
        "cached": usage.get("cache_read_input_token_count", 0),
    })


def investigator(**settings) -> Agent:
    """The agent, with any extra Agent settings (such as a compaction strategy) passed through."""
    client = make_client()
    client.function_invocation_configuration["max_iterations"] = 9
    return Agent(client, INSTRUCTIONS, name="investigator", tools=TOOLS, middleware=[meter], **settings)


def show(result: AgentResponse) -> None:
    """Print each tool call, then the answer."""
    for message in result.messages[:-1]:
        for content in message.contents:
            if content.type == "function_call":
                print(f"Model asks: {content.name}({content.arguments})")
    print(f"\n{result.messages[-1].text}")
