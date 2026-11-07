"""Chapter 7 demo: where the shipment records note lands on every model call of a run, with the history saved
once per run (the default) or after every model call. The history provider is listed first in both.

    uv run python ch07/per_call_order.py
    uv run python ch07/per_call_order.py --per-call
"""

import asyncio
import sys

from agent_framework import InMemoryHistoryProvider

from cobalt import release_sh4471
from investigate import FIRST_TASK, STILL_HELD, investigator
from providers import ShipmentStatus

per_call = "--per-call" in sys.argv


def print_sources(messages) -> None:
    runs = []  # consecutive messages from the same source, as [source, count]
    for message in messages:
        source = message.additional_properties.get("_attribution", {}).get("source_id", "the caller")
        if runs and runs[-1][0] == source:
            runs[-1][1] += 1
        else:
            runs.append([source, 1])
    print("  " + ", ".join(f"{source} x{count}" for source, count in runs))


def watch_requests(client) -> None:
    """Print each request's messages at the client's last step before it is sent. Middleware would see the
    messages too early: with saving after every model call, the framework loads the history after it."""
    send = client._inner_get_response  # a private method, used here only to observe

    def watched(*, messages, **kwargs):
        print_sources(messages)
        return send(messages=messages, **kwargs)

    client._inner_get_response = watched


async def main() -> None:
    agent = investigator(
        context_providers=[InMemoryHistoryProvider(), ShipmentStatus()],
        require_per_service_call_history_persistence=per_call,
    )
    session = agent.create_session()
    await agent.run(FIRST_TASK, session=session)
    release_sh4471()
    watch_requests(agent.client)
    print(f"History saved {'after every model call' if per_call else 'once per run'}.")
    print(f"Run 2: {STILL_HELD}\nEach model call's messages, in order, by where they came from:")
    await agent.run(STILL_HELD, session=session)


asyncio.run(main())
