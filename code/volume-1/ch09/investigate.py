"""Chapter 9's investigation agent: Chapter 8's, with a tool that refiles documents."""

import json
import logging
import uuid
from pathlib import Path

from agent_framework import Agent, AgentResponse, AgentSession, Message

from agentlab.llm import make_client
from cobalt import READ_TOOLS, refile_document

# Keep framework warnings, such as an ignored approval response, out of the transcripts: each
# program prints what ran instead.
logging.getLogger("agent_framework").setLevel(logging.ERROR)

INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight's operations team.

Goal: find the root cause of a delay and the action that would fix it.

How to work:
- Use the tools to check facts. Never guess a status, case number or document location.
- Before each tool call, say in one sentence what you want to find out.
- A hold or a delay is a symptom. Keep investigating until you find what caused it,
  or until no tool can tell you more.

Limits:
- Never refile a document without the analyst's approval.

Answer format:
Cause: one sentence.
Evidence: the facts that show it, with IDs.
Recommended action: one sentence."""

# With the approval held in code, the instructions describe the process instead of standing guard over it.
GATED_INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight's operations team.

Goal: find the root cause of a delay and the action that would fix it.

How to work:
- Use the tools to check facts. Never guess a status, case number or document location.
- Before each tool call, say in one sentence what you want to find out.
- A hold or a delay is a symptom. Keep investigating until you find what caused it,
  or until no tool can tell you more.

Limits:
- If a document is misfiled, call refile_document to fix it. Every refiling waits for an
  analyst's approval before it runs; the analyst sees exactly what you asked for.

Answer format:
Cause: one sentence.
Evidence: the facts that show it, with IDs.
Recommended action: one sentence."""

TASK = "Shipment SH-4471 is three days late. Find out why."
USER_ID = "analyst-207"  # who the run is for, set by the program, never by the model
PENDING = Path(__file__).parent / "state" / "pending"


def run_args(user_id: str = USER_ID) -> dict:
    """Runtime values for one run, which tools and middleware can read and the model can't set."""
    return {"user_id": user_id, "run_id": uuid.uuid4().hex[:12]}


def investigator(refile_tool=refile_document, instructions: str = GATED_INSTRUCTIONS, **settings) -> Agent:
    client = make_client()
    client.function_invocation_configuration["max_iterations"] = 9
    return Agent(client, instructions, name="investigator", tools=[*READ_TOOLS, refile_tool], **settings)


def show(result: AgentResponse) -> None:
    """Print each tool call and its result, then the last message's text."""
    for message in result.messages:
        for content in message.contents:
            if content.type == "function_call":
                print(f"Model asks: {content.name}({content.arguments})")
            elif content.type == "function_result":
                print(f"   Result: {json.dumps(content.result) if not isinstance(content.result, str) else content.result}")
    if result.messages and result.messages[-1].text:
        print(f"\n{result.messages[-1].text}")


def save_pending(session: AgentSession, result: AgentResponse) -> str:
    """Save the session and the requests the run returned, for a program that answers them later."""
    PENDING.mkdir(parents=True, exist_ok=True)
    request = result.user_input_requests[0]
    entry = {"session": session.to_dict(), "request": request.to_dict()}
    (PENDING / f"{request.id}.json").write_text(json.dumps(entry, indent=2))
    return request.id


def answer(request, approved: bool) -> Message:
    """The message that carries a person's decision on one approval request
    back to the agent."""
    response = request.to_function_approval_response(approved)
    return Message(role="user", contents=[response])
