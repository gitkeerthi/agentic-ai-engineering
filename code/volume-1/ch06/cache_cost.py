"""Chapter 6 demo: the same four questions with no compaction, with truncation before every model call, or with
truncation of the stored history after each run. What does each cost once the provider's cache is counted?

    uv run python ch06/cache_cost.py --mode none
    uv run python ch06/cache_cost.py --mode every-call
    uv run python ch06/cache_cost.py --mode stored
"""

import argparse
import asyncio

from agent_framework import CharacterEstimatorTokenizer, CompactionProvider, InMemoryHistoryProvider, TruncationStrategy

from investigate import FIRST_TASK, FOLLOW_UP, GO_BACK, SECOND_TASK, calls, investigator

tokenizer = CharacterEstimatorTokenizer()
CACHED_PRICE = 1 / 50  # cached input costs a fiftieth of uncached input at the lab model's prices

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--mode", choices=["none", "every-call", "stored"], default="none")
mode = parser.parse_args().mode


def truncation() -> TruncationStrategy:
    return TruncationStrategy(max_n=1_200, compact_to=700, tokenizer=tokenizer)


if mode == "every-call":
    agent = investigator(compaction_strategy=truncation(), tokenizer=tokenizer)
elif mode == "stored":
    # Leave out what compaction marked.
    history = InMemoryHistoryProvider(skip_excluded=True)
    compaction = CompactionProvider(
        after_strategy=truncation(),
        tokenizer=tokenizer,
        history_source_id=history.source_id,
    )
    agent = investigator(context_providers=[history, compaction])
else:
    agent = investigator()


async def main() -> None:
    session = agent.create_session()
    print(f"Compaction: {mode}\n")
    print(f"{'Call':>4}  {'Question':<10}{'Input':>7}{'Cached':>8}")
    for number, question in enumerate([FIRST_TASK, FOLLOW_UP, SECOND_TASK, GO_BACK], start=1):
        first = len(calls)
        result = await agent.run(question, session=session)
        for index, call in enumerate(calls[first:], start=first + 1):
            print(f"{index:>4}  {f'Q{number}':<10}{call['input']:>7,}{call['cached']:>8,}")
        stored = session.state["in_memory"]["messages"]
        left_out = sum(1 for m in stored if m.additional_properties.get("_excluded"))
        print(f"      stored after Q{number}: {len(stored)} messages, {left_out} marked to leave out")
    total = sum(c["input"] for c in calls)
    cached = sum(c["cached"] for c in calls)
    units = total - cached + cached * CACHED_PRICE
    print(f"\n{len(calls)} model calls, {total:,} input tokens, {cached:,} cached")
    print(f"Input cost in uncached-token units: {units:,.0f}")
    print(f"\nLast answer: {result.messages[-1].text}")


asyncio.run(main())
