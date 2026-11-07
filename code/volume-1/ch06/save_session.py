"""Chapter 6 demo: keep a session across a restart. `save` investigates and writes the session to a file;
`resume`, run as a new process, reads it back and asks the follow-up.

    uv run python ch06/save_session.py save
    uv run python ch06/save_session.py resume
"""

import asyncio
import json
import sys
from pathlib import Path

from agent_framework import AgentSession

from investigate import FIRST_TASK, FOLLOW_UP, calls, investigator, show

# A stand-in for the database of Volume 2.
SAVED = Path(__file__).parent / "saved-session.json"


async def save() -> None:
    agent = investigator()
    session = agent.create_session()
    print(f"Run 1: {FIRST_TASK}\n")
    show(await agent.run(FIRST_TASK, session=session))
    SAVED.write_text(json.dumps(session.to_dict(), indent=2))
    print(f"\nSaved session {session.session_id} to {SAVED.name}: {SAVED.stat().st_size:,} bytes")


async def resume() -> None:
    agent = investigator()
    session = AgentSession.from_dict(json.loads(SAVED.read_text()))
    print(f"Restored session {session.session_id}: {len(session.state['in_memory']['messages'])} messages\n")
    print(f"Run 2: {FOLLOW_UP}\n")
    show(await agent.run(FOLLOW_UP, session=session))
    print(f"\nModel calls: {len(calls)}")


asyncio.run(save() if sys.argv[1] == "save" else resume())
