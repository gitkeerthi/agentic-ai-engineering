"""Chapter 7 demo: the stale customer update again, with the program putting SH-4471's current record in
front of the question.

    uv run python ch07/by_hand.py
"""

import asyncio
import json

from cobalt import SHIPMENTS, release_sh4471
from investigate import CUSTOMER_UPDATE, FIRST_TASK, calls, investigator, show


def with_current_record(question: str, shipment_id: str) -> str:
    record = json.dumps(SHIPMENTS[shipment_id])
    return (f"Current record for {shipment_id}, looked up just now: {record}"
            f"\n\n{question}")


async def main() -> None:
    agent = investigator()
    session = agent.create_session()

    print(f"Run 1: {FIRST_TASK}\n")
    show(await agent.run(FIRST_TASK, session=session))

    release_sh4471()
    print("\n(The team refiles the invoice. Customs clears RTM-88213 and releases SH-4471.)")

    task = with_current_record(CUSTOMER_UPDATE, "SH-4471")
    calls_before = len(calls)
    print(f"\nRun 2: {CUSTOMER_UPDATE}\nSent: {task!r}\n")
    show(await agent.run(task, session=session))
    print(f"\nModel calls in run 2: {len(calls) - calls_before}")


asyncio.run(main())
