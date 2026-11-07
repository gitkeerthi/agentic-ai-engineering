"""Chapter 6 demo: the same two runs in one session, then what the session holds.

    uv run python ch06/session.py
"""

import asyncio
from collections import Counter

from investigate import FIRST_TASK, FOLLOW_UP, calls, investigator, show


async def main() -> None:
    agent = investigator()
    session = agent.create_session()

    print(f"Run 1: {FIRST_TASK}\n")
    show(await agent.run(FIRST_TASK, session=session))
    first_run_calls = len(calls)

    print(f"\nRun 2: {FOLLOW_UP}\n")
    show(await agent.run(FOLLOW_UP, session=session))
    print(f"\nModel calls: run 1 made {first_run_calls}, run 2 made {len(calls) - first_run_calls}.")

    print(f"\nThe session: id {session.session_id}, state keys {list(session.state)}")
    messages = session.state["in_memory"]["messages"]
    kinds = Counter(f"{m.role}: {', '.join(c.type for c in m.contents)}" for m in messages)
    print(f"{len(messages)} messages stored:")
    for kind, count in kinds.items():
        print(f"  {count} x {kind}")


asyncio.run(main())
