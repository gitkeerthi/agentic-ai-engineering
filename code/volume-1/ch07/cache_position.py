"""Chapter 7 demo: where a provider's note lands, and what that does to the provider's prompt cache.
Three runs in one session; SH-4471's record changes before runs 2 and 3, so the note changes too.
For each run, the first model call's input tokens and how many of them were read from the cache, then the
answers in full.

    uv run python ch07/cache_position.py --place after-history
    uv run python ch07/cache_position.py --place before-history
    uv run python ch07/cache_position.py --place instructions
"""

import argparse
import asyncio

from agent_framework import InMemoryHistoryProvider

from cobalt import pick_up_sh4471, release_sh4471
from investigate import CUSTOMER_UPDATE, FIRST_TASK, calls, investigator
from providers import ShipmentStatus

WHERE_NOW = "Where is SH-4471 now?"


class ShipmentStatusAsInstructions(ShipmentStatus):
    """The same note, added to the instructions instead of as a message."""

    async def before_run(self, *, agent, session, context, state) -> None:
        if note := self.current_records(state):
            context.extend_instructions(self.source_id, note)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--place", choices=["after-history", "before-history", "instructions"], required=True)
place = parser.parse_args().place
providers = {
    "after-history": [InMemoryHistoryProvider(), ShipmentStatus()],
    "before-history": [ShipmentStatus()],
    "instructions": [ShipmentStatusAsInstructions()],
}[place]


async def main() -> None:
    agent = investigator(context_providers=providers)
    session = agent.create_session()
    print(f"Note placed: {place}\n")
    print(f"{'Run':<34}{'Input':>7}{'Cached':>8}")
    answers = []
    for change, question in [(None, FIRST_TASK), (release_sh4471, CUSTOMER_UPDATE), (pick_up_sh4471, WHERE_NOW)]:
        if change:
            change()
        first = len(calls)
        result = await agent.run(question, session=session)
        answers.append((question, result.messages[-1].text.strip()))
        print(f"{question[:33]:<34}{calls[first]['input']:>7}{calls[first]['cached']:>8}")
    for question, answer in answers[1:]:
        print(f"\n{question}\n{answer}")


asyncio.run(main())
