"""Chapter 7 demo: the stale customer update again, with an instruction to look records up again before
stating them.

    uv run python ch07/instructed.py
"""

import asyncio

from cobalt import release_sh4471
from investigate import CUSTOMER_UPDATE, FIRST_TASK, calls, investigator, show

INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight's operations team.

Goal: find the root cause of a delay and the action that would fix it.

How to work:
- Use the tools to check facts. Never guess a status, case number or document location.
- Records change while a conversation goes on. Before you state a shipment's status, location
  or documents, look them up again, even if you looked them up earlier in the conversation.
- Before each tool call, say in one sentence what you want to find out.
- A hold or a delay is a symptom. Keep investigating until you find what caused it,
  or until no tool can tell you more.

Limits:
- You can only read Cobalt's systems. Recommend actions; never claim to have taken one.

Answer format:
Cause: one sentence.
Evidence: the facts that show it, with IDs.
Recommended action: one sentence."""


async def main() -> None:
    agent = investigator(INSTRUCTIONS)
    session = agent.create_session()

    print(f"Run 1: {FIRST_TASK}\n")
    show(await agent.run(FIRST_TASK, session=session))

    release_sh4471()
    print("\n(The team refiles the invoice. Customs clears RTM-88213 and releases SH-4471.)")

    calls_before = len(calls)
    print(f"\nRun 2: {CUSTOMER_UPDATE}\n")
    show(await agent.run(CUSTOMER_UPDATE, session=session))
    print(f"\nModel calls in run 2: {len(calls) - calls_before}")


asyncio.run(main())
