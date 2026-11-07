"""Chapter 6 demo: one compaction strategy, applied to the same saved conversation, then a question about its start.

Run conversation.py first: it saves the conversation this program loads. The limits below are far smaller than a
real agent would use, so each strategy has something to remove from a short conversation.

    uv run python ch06/compaction.py --strategy none
    uv run python ch06/compaction.py --strategy sliding-window
"""

import argparse
import asyncio
import json
from pathlib import Path

from agent_framework import (
    GROUP_ANNOTATION_KEY,
    SUMMARY_OF_GROUP_IDS_KEY,
    AgentSession,
    CharacterEstimatorTokenizer,
    SelectiveToolCallCompactionStrategy,
    SlidingWindowStrategy,
    SummarizationStrategy,
    TokenBudgetComposedStrategy,
    ToolResultCompactionStrategy,
    TruncationStrategy,
    included_messages,
)

from agentlab.llm import make_client
from investigate import GO_BACK, calls, investigator, show

tokenizer = CharacterEstimatorTokenizer()  # about four characters a token
STRATEGIES = {
    "none": None,
    "sliding-window": SlidingWindowStrategy(keep_last_groups=5),
    "truncation": TruncationStrategy(max_n=2_000, compact_to=1_500, tokenizer=tokenizer),
    "tool-results": ToolResultCompactionStrategy(keep_last_tool_call_groups=1),
    "drop-tool-calls": SelectiveToolCallCompactionStrategy(keep_last_tool_call_groups=1),
    "summary": SummarizationStrategy(client=make_client(), target_count=4, threshold=2),
    "budget": TokenBudgetComposedStrategy(
        token_budget=2_000,
        tokenizer=tokenizer,
        strategies=[
            ToolResultCompactionStrategy(keep_last_tool_call_groups=1),
            SummarizationStrategy(
                client=make_client(), target_count=4, threshold=2
            ),
            SlidingWindowStrategy(keep_last_groups=5),
        ],
    ),
}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--strategy", choices=STRATEGIES, default="none")
choice = parser.parse_args().strategy


class Recorded:
    """Wraps a strategy and records the messages it leaves in each model call. A lab instrument, not production code."""

    def __init__(self, strategy):
        self.strategy = strategy
        self.sent: list[list] = []

    async def __call__(self, messages: list) -> bool:
        changed = await self.strategy(messages) if self.strategy else False
        self.sent.append(included_messages(messages))
        return changed


def describe(message) -> str:
    parts = []
    for content in message.contents:
        if content.type == "function_call":
            parts.append(f"asks {content.name}({content.arguments})")
        elif content.type == "function_result":
            parts.append(f"result {str(content.result)[:60]}")
        elif content.type == "text" and content.text.strip():
            parts.append(repr(content.text.strip()[:60]))
    return f"{message.role}: {'; '.join(parts)}"


async def main() -> None:
    saved = json.loads((Path(__file__).parent / "conversation.json").read_text())
    session = AgentSession.from_dict(saved)
    recorded = Recorded(STRATEGIES[choice])
    agent = investigator(compaction_strategy=recorded, tokenizer=tokenizer)
    print(f"Question: {GO_BACK}  (compaction: {choice})\n")
    show(await agent.run(GO_BACK, session=session))

    first = calls[-len(recorded.sent)]
    print(f"\nSent in the first model call: {len(recorded.sent[0])} messages, {first['input']:,} input tokens, {first['cached']:,} cached")
    for message in recorded.sent[0]:
        print(f"  {describe(message)}")
    stored = session.state["in_memory"]["messages"]
    for message in recorded.sent[0]:
        if SUMMARY_OF_GROUP_IDS_KEY in message.additional_properties.get(GROUP_ANNOTATION_KEY, {}):
            print(f"\nWritten by the strategy, not stored:\n{message.text}")
    print(f"\nModel calls this run: {len(recorded.sent)}. Stored in the session: {len(stored)} messages")


asyncio.run(main())
