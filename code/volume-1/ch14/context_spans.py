"""Chapter 14 demo, no model: what the trace shows of context retrieval and memory, the work a context provider
and a history provider do before and after a run. The agent replies from a script; sensitive data is off.

    uv run python ch14/context_spans.py [--span]

Without --span, the providers run untraced, as the framework leaves them. With --span, each provider wraps its
work in a span of its own that records what it read or stored by count and ID, not by content.
"""

import argparse
import asyncio
import shutil

from agent_framework import Agent, ContextProvider, InMemoryHistoryProvider, Message
from agent_framework.observability import get_tracer

import telemetry
from cobalt import SHIPMENTS
from scripted import ScriptedClient
from show import load, print_trace

tracer = get_tracer(telemetry.SCOPE)

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument(
    "--span", action="store_true", help="give each provider's work a span"
)
args = parser.parse_args()


class CurrentStatus(ContextProvider):
    """Before each run, adds SH-4471's current record: Chapter 7's dynamic context, cut down."""

    def __init__(self) -> None:
        super().__init__("current_status")

    async def before_run(self, *, agent, session, context, state) -> None:
        if not args.span:
            context.extend_messages(
                self, [Message("user", [f"SH-4471: {SHIPMENTS['SH-4471']}"])]
            )
            return
        with tracer.start_as_current_span(
            "context current_status"
        ) as span:
            context.extend_messages(
                self, [Message("user", [f"SH-4471: {SHIPMENTS['SH-4471']}"])]
            )
            span.set_attributes(
                {"cobalt.record_ids": ["SH-4471"], "cobalt.messages_added": 1}
            )


class TracedHistory(InMemoryHistoryProvider):
    """The framework's in-memory history, with a span around each load and save when --span is given."""

    async def get_messages(self, session_id, **kwargs):
        if not args.span:
            return await super().get_messages(session_id, **kwargs)
        with tracer.start_as_current_span("memory load") as span:
            messages = await super().get_messages(session_id, **kwargs)
            span.set_attribute("cobalt.messages", len(messages))
            return messages

    async def save_messages(self, session_id, messages, **kwargs):
        if not args.span:
            return await super().save_messages(session_id, messages, **kwargs)
        with tracer.start_as_current_span("memory save") as span:
            span.set_attribute("cobalt.messages", len(messages))
            return await super().save_messages(session_id, messages, **kwargs)


name = "context-span" if args.span else "context"
shutil.rmtree(telemetry.HERE / "store" / name, ignore_errors=True)
store = telemetry.setup(name)
agent = Agent(
    ScriptedClient(["SH-4471 is held in Rotterdam.", "Still held."]),
    "Answer from the records you're given.",
    name="assistant",
    context_providers=[TracedHistory(), CurrentStatus()],
)


async def main() -> None:
    session = agent.create_session()
    for task in ("Where is SH-4471?", "And now?"):
        with tracer.start_as_current_span("request"):
            await agent.run(task, session=session)


asyncio.run(main())
telemetry.close()
for root in [s for s in load(store, "spans") if s["parent_id"] is None]:
    print_trace(store, root["context"]["trace_id"][2:])
