"""Chapter 7 demo: the agent investigates SH-4471 in a session; the team's fix then releases the shipment;
a second run in the same session asks for a customer update.

    uv run python ch07/stale_update.py
    uv run python ch07/stale_update.py --still-held   # ask whether it is still held instead
"""

import asyncio
import sys

from cobalt import release_sh4471
from investigate import CUSTOMER_UPDATE, FIRST_TASK, STILL_HELD, calls, investigator, show

question = STILL_HELD if "--still-held" in sys.argv else CUSTOMER_UPDATE


async def main() -> None:
    agent = investigator()
    session = agent.create_session()

    print(f"Run 1: {FIRST_TASK}\n")
    show(await agent.run(FIRST_TASK, session=session))

    release_sh4471()
    print("\n(The team refiles the invoice. Customs clears RTM-88213 and releases SH-4471.)")

    calls_before = len(calls)
    print(f"\nRun 2: {question}\n")
    show(await agent.run(question, session=session))
    print(f"\nModel calls in run 2: {len(calls) - calls_before}")


asyncio.run(main())
