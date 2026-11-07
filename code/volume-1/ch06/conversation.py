"""Chapter 6 demo: three questions in one session. How does each model call grow? The session is saved to
conversation.json, so compaction.py can try each strategy on the same history.

    uv run python ch06/conversation.py
"""

import asyncio
import json
from pathlib import Path

from investigate import FIRST_TASK, FOLLOW_UP, SECOND_TASK, calls, investigator, show

SAVED = Path(__file__).parent / "conversation.json"


async def main() -> None:
    agent = investigator()
    session = agent.create_session()
    for number, question in enumerate([FIRST_TASK, FOLLOW_UP, SECOND_TASK], start=1):
        first_call = len(calls)
        print(f"Question {number}: {question}\n")
        show(await agent.run(question, session=session))
        print(f"\n{'Call':>6}{'Messages sent':>15}{'Input tokens':>14}{'Cached':>8}")
        for index, call in enumerate(calls[first_call:], start=first_call + 1):
            print(f"{index:>6}{call['messages']:>15}{call['input']:>14,}{call['cached']:>8,}")
        print()
    total_input = sum(c["input"] for c in calls)
    total_cached = sum(c["cached"] for c in calls)
    print(f"{len(calls)} model calls, {total_input:,} input tokens, {total_cached:,} of them cached")
    SAVED.write_text(json.dumps(session.to_dict(), indent=2))
    print(f"Saved {len(session.state['in_memory']['messages'])} messages to {SAVED.name}")


asyncio.run(main())
