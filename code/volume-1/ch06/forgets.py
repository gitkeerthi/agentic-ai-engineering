"""Chapter 6 demo: two runs with no session. The second run can't see what the first one found.

    uv run python ch06/forgets.py
"""

import asyncio

from investigate import FIRST_TASK, FOLLOW_UP, investigator, show


async def main() -> None:
    agent = investigator()

    print(f"Run 1: {FIRST_TASK}\n")
    show(await agent.run(FIRST_TASK))

    print(f"\nRun 2: {FOLLOW_UP}\n")
    show(await agent.run(FOLLOW_UP))


asyncio.run(main())
