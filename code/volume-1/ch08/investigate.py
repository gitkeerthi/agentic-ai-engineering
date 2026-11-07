"""Chapter 8's investigation agent and the tasks its programs give it."""

import uuid

from agent_framework import Agent, AgentResponse

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

TASK = "Shipment SH-4471 is three days late. Find out why."
WITH_UPDATE = "Shipment SH-4471 is three days late. Find out why, then draft a two-line update to the customer's contact."
USER_ID = "analyst-207"  # who the runs are for: set by the program, never the model


def run_args(user_id: str = USER_ID) -> dict:
    """Runtime values for one run: who it's for, and an ID that ties
    the run's audit records together."""
    return {"user_id": user_id, "run_id": uuid.uuid4().hex[:12]}


def investigator(tools=TOOLS, max_iterations: int = 9, **settings) -> Agent:
    """The agent, with other tools, another loop limit or extra Agent settings (such as middleware) if given."""
    client = make_client()
    client.function_invocation_configuration["max_iterations"] = max_iterations
    return Agent(client, INSTRUCTIONS, name="investigator", tools=tools, **settings)


def show(result: AgentResponse) -> None:
    """Print each tool call, then the last message's text."""
    for message in result.messages:
        for content in message.contents:
            if content.type == "function_call":
                print(f"Model asks: {content.name}({content.arguments})")
    print(f"\n{result.messages[-1].text}")


# The framework's text for a tool call that an Agent Hooks deny blocked
HOOKS_BLOCK = "Tool call blocked by agent-hooks"


def outcome(result: AgentResponse) -> str:
    """What the run's ending means for the program, read from flags and
    structure, never from the text."""
    results = [c for m in result.messages for c in m.contents
               if c.type == "function_result"]
    failed = [c for c in results if c.exception]  # ①
    blocked = [c for c in results if HOOKS_BLOCK in str(c.result)]
    notes = [f"{len(failed)} failed tool call(s)"] if failed else []
    if blocked:
        notes.append(f"{len(blocked)} tool call(s) blocked by Agent Hooks")
    note = f" after {' and '.join(notes)}" if notes else ""
    if result.additional_properties.get("limit_reached"):  # ②
        return f"partial: a loop limit was reached{note}"
    if result.additional_properties.get("budget_spent"):
        return f"partial: the token budget was spent{note}"
    last = result.messages[-1]
    if last.role == "tool":  # ③
        stops = [c.result for c in last.contents if c.type == "function_result"
                 and str(c.result).startswith("Stopped:")]
        reason = stops[0] if stops else "no reason recorded"
        return f"stopped by middleware{note}: {reason}"
    if result.finish_reason != "stop":  # ④
        ending = result.finish_reason
        return f"unclear: the run ended with finish_reason {ending}{note}"
    if notes:  # ⑤
        return f"unclear: the model answered{note}"
    return "answer"
