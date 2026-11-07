"""Chapter 7 demo: what happens before and after a run. Two small context providers report when they are called
and add a message and an instruction each; a chat middleware prints what the model was sent. Two runs in one
session, with no tools, so each run makes one model call.

    uv run python ch07/pipeline.py
"""

import asyncio

from agent_framework import Agent, ChatContext, ContextProvider, Message, chat_middleware

from agentlab.llm import make_client


class Labeled(ContextProvider):
    """Adds one message and one instruction, both carrying its name,
    and reports each call."""

    async def before_run(self, *, agent, session, context, state) -> None:
        print(f"  before_run: {self.source_id}")
        note = Message("user", [f"(message from {self.source_id})"])
        context.extend_messages(self, [note])
        context.extend_instructions(
            self.source_id, f"(instruction from {self.source_id})"
        )

    async def after_run(self, *, agent, session, context, state) -> None:
        count = len(context.response.messages)
        print(f"  after_run:  {self.source_id} (the response has {count} message)")


@chat_middleware
async def print_sent(context: ChatContext, call_next) -> None:
    print("  The model is sent:")
    print(f"    instructions: {context.options.get('instructions')!r}")
    for message in context.messages:
        source = message.additional_properties.get("_attribution", {}).get("source_id", "the caller")
        print(f"    {message.role:<9} from {source:<10} {message.text[:60]!r}")
    await call_next()


async def main() -> None:
    agent = Agent(
        make_client(),
        "Answer in five words or fewer.",
        context_providers=[Labeled("first"), Labeled("second")],
        middleware=[print_sent],
    )
    session = agent.create_session()
    for question in ["Name a port in the Netherlands.", "Name one in Belgium."]:
        print(f"\nRun: {question}")
        result = await agent.run(question, session=session)
        print(f"  Answer: {result.text}")
    print(f"\nProviders after the runs: {[p.source_id for p in agent.context_providers]}")
    stored = session.state["in_memory"]["messages"]
    print(f"Stored history: {[(m.role, m.text) for m in stored]}")


asyncio.run(main())
