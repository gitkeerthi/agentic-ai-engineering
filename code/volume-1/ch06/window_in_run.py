"""Chapter 6 demo: a sliding window smaller than one investigation. Compaction runs before every model call,
including those inside a run, so the window can drop the run's own task.

    uv run python ch06/window_in_run.py
"""

import asyncio

from agent_framework import CharacterEstimatorTokenizer, SlidingWindowStrategy, included_messages

from investigate import FIRST_TASK, investigator, show

sent: list[list] = []


class Recorded:
    """Wraps a strategy and records the messages it leaves in each model call. A lab instrument, not production code."""

    def __init__(self, strategy):
        self.strategy = strategy

    async def __call__(self, messages: list) -> bool:
        changed = await self.strategy(messages)
        sent.append(included_messages(messages))
        return changed


async def main() -> None:
    window = Recorded(SlidingWindowStrategy(keep_last_groups=3))
    agent = investigator(compaction_strategy=window, tokenizer=CharacterEstimatorTokenizer())
    print(f"Task: {FIRST_TASK}  (compaction: the last 3 groups)\n")
    show(await agent.run(FIRST_TASK, session=agent.create_session()))
    print("\nModel call  Messages sent  Task included")
    for number, messages in enumerate(sent, start=1):
        has_task = any(m.role == "user" for m in messages)
        print(f"{number:>10}  {len(messages):>13}  {'yes' if has_task else 'no'}")


asyncio.run(main())
