"""Chapter 7 demo: the stale customer update again, with a context provider that puts the current record of every
shipment the session has looked up in front of the model on every run.

    uv run python ch07/status_provider.py
    uv run python ch07/status_provider.py --after-history   # list the history provider first
"""

import asyncio
import sys

from agent_framework import InMemoryHistoryProvider

from cobalt import release_sh4471
from investigate import CUSTOMER_UPDATE, FIRST_TASK, calls, investigator, show
from providers import ShipmentStatus

if "--after-history" in sys.argv:
    providers = [InMemoryHistoryProvider(), ShipmentStatus()]
else:
    # The framework adds the history provider after it.
    providers = [ShipmentStatus()]


async def main() -> None:
    agent = investigator(context_providers=providers)
    session = agent.create_session()

    print(f"Run 1: {FIRST_TASK}\n")
    show(await agent.run(FIRST_TASK, session=session))
    print(f"\nThe provider's state: {session.state['shipment_status']}")

    release_sh4471()
    print("\n(The team refiles the invoice. Customs clears RTM-88213 and releases SH-4471.)")

    calls_before = len(calls)
    print(f"\nRun 2: {CUSTOMER_UPDATE}\n")
    show(await agent.run(CUSTOMER_UPDATE, session=session))
    print(f"\nModel calls in run 2: {len(calls) - calls_before}")
    print(f"Providers, in order: {[p.source_id for p in agent.context_providers]}")

    stored = session.state["in_memory"]["messages"]
    print(f"Stored: {len(stored)} messages, of which from the provider: "
          f"{sum('Current shipment records' in m.text for m in stored)}")


asyncio.run(main())
