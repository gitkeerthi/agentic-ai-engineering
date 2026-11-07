"""Chapter 6 check, with canned replies in place of the model: what a chat middleware sees, what an agent-level
strategy keeps, what reaches the request, and which exclusion marks a run saves in the session.

It makes no model call and costs nothing. Run conversation.py first: part 1 loads the conversation it saves.

    uv run python ch06/middleware_view.py
"""

import asyncio
import json
from pathlib import Path

from agent_framework import (
    EXCLUDED_KEY,
    AgentSession,
    CharacterEstimatorTokenizer,
    SlidingWindowStrategy,
    included_messages,
)
from openai.types.chat import ChatCompletion

import agentlab.llm
from investigate import FIRST_TASK, FOLLOW_UP, GO_BACK, calls, investigator

agentlab.llm.record = lambda *args: None  # canned replies use no tokens, so keep them out of the usage log


class Recorded:
    """Wraps a strategy and records, for each model call, how many messages it kept and whether the task was one."""

    def __init__(self, strategy):
        self.strategy = strategy
        self.kept: list[int] = []
        self.task_kept: list[bool] = []

    async def __call__(self, messages: list) -> bool:
        changed = await self.strategy(messages)
        kept = included_messages(messages)
        self.kept.append(len(kept))
        self.task_kept.append(any(m.role == "user" for m in kept))
        return changed


def canned(agent, script: list) -> list[int]:
    """Answer the agent's requests from a script, at the OpenAI library beneath every framework layer.

    Each step is a reply text, or a (tool name, arguments) pair for one tool request. Returns a list that
    collects how many messages each request carried.
    """
    sent: list[int] = []

    async def create(*args, **kwargs):
        sent.append(len(kwargs["messages"]))
        step = script.pop(0)
        message = {"role": "assistant", "content": step if isinstance(step, str) else None}
        if not isinstance(step, str):
            name, arguments = step
            message["tool_calls"] = [{
                "id": f"call_{len(sent)}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }]
        return ChatCompletion.model_validate({
            "id": f"canned-{len(sent)}", "object": "chat.completion", "created": 0, "model": "canned",
            "choices": [{"index": 0, "message": message,
                         "finish_reason": "stop" if isinstance(step, str) else "tool_calls"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    agent.client.client.chat.completions.create = create
    return sent


async def go_back() -> None:
    print("1. The go-back question on the saved conversation, five-group window on the agent")
    saved = json.loads((Path(__file__).parent / "conversation.json").read_text())
    session = AgentSession.from_dict(saved)
    recorded = Recorded(SlidingWindowStrategy(keep_last_groups=5))
    agent = investigator(compaction_strategy=recorded, tokenizer=CharacterEstimatorTokenizer())
    sent = canned(agent, ["Canned answer."])
    calls.clear()
    await agent.run(GO_BACK, session=session)
    print(f"   chat middleware (meter) saw:          {calls[0]['messages']} messages")
    print(f"   the strategy kept:                    {recorded.kept[0]} messages")
    print(f"   the provider request carried:         {sent[0]} messages")
    print("   (the kept 7, plus the instructions, with one stored message of three tool results sent as three)")


async def in_run() -> AgentSession:
    print("\n2. A fresh investigation with a three-group window on the agent (scripted replies)")
    recorded = Recorded(SlidingWindowStrategy(keep_last_groups=3))
    agent = investigator(compaction_strategy=recorded, tokenizer=CharacterEstimatorTokenizer())
    sent = canned(agent, [
        ("get_shipment_status", {"shipment_id": "SH-4471"}),
        ("get_customs_case", {"case_id": "RTM-88213"}),
        ("list_required_documents", {"case_id": "RTM-88213"}),
        ("find_document", {"shipment_id": "SH-4471", "document_type": "commercial invoice"}),
        "Cause: canned answer.",
    ])
    calls.clear()
    session = agent.create_session()
    await agent.run(FIRST_TASK, session=session)
    print("   Model call  Middleware saw  Strategy kept  Task kept  Provider request")
    rows = zip([c["messages"] for c in calls], recorded.kept, recorded.task_kept, sent)
    for n, (seen, kept, task, request) in enumerate(rows, start=1):
        print(f"   {n:>10}  {seen:>14}  {kept:>13}  {'yes' if task else 'no':>9}  {request:>16}")
    stored = session.state["in_memory"]["messages"]
    marked = [m for m in stored if m.additional_properties.get(EXCLUDED_KEY)]
    print(f"   Stored after the run: {len(stored)} messages, {len(marked)} with an exclusion mark")
    for m in stored:
        kinds = ", ".join(c.type for c in m.contents)
        print(f"     {m.role}: {kinds}{'  (marked excluded)' if m.additional_properties.get(EXCLUDED_KEY) else ''}")
    return session


async def next_run(session: AgentSession) -> None:
    print("\n3. A second run in the same session, by a new agent, after those marks were saved")
    for label, strategy in [("no strategy", None), ("a window of 100 groups", SlidingWindowStrategy(keep_last_groups=100))]:
        recorded = Recorded(strategy) if strategy else None
        settings = {"compaction_strategy": recorded, "tokenizer": CharacterEstimatorTokenizer()} if recorded else {}
        agent = investigator(**settings)
        sent = canned(agent, ["Canned answer."])
        calls.clear()
        stored = session.state["in_memory"]["messages"]
        loaded = len(stored)
        marked = sum(1 for m in stored if m.additional_properties.get(EXCLUDED_KEY))
        await agent.run(FOLLOW_UP, session=session)
        print(f"   With {label}:")
        print(f"     loaded from the session:  {loaded} messages, {marked} of them marked excluded")
        print(f"     chat middleware saw:      {calls[0]['messages']} (the loaded messages and the new question)")
        if recorded:
            left_out = calls[0]["messages"] - recorded.kept[0]
            print(f"     the strategy kept:        {recorded.kept[0]} (it left out {left_out}, the marked messages)")
        else:
            print("     no strategy ran, so the marks were ignored and every message was sent")
        print(f"     the provider request:     {sent[0]} (the messages sent, plus the instructions)")


async def main() -> None:
    await go_back()
    session = await in_run()
    await next_run(session)


asyncio.run(main())
