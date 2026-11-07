"""A local log of every model call's token usage, and what this month's calls have cost.

Print the month's total with: uv run python -m agentlab.usage
"""

import json
from datetime import UTC, datetime
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "usage.jsonl"


def record(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> None:
    """Append one call's token counts to the log. Cached tokens are the part of the input the provider had cached."""
    entry = {
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": model,
        "input": input_tokens,
        "cached": cached_tokens,
        "output": output_tokens,
    }
    with LOG.open("a") as log:
        log.write(json.dumps(entry) + "\n")


def mark() -> int:
    """How many calls the log holds now; pass it to since() to total the calls made after this point."""
    return len(LOG.read_text().splitlines()) if LOG.exists() else 0


def since(start: int) -> str:
    """The calls logged after mark() returned start: how many, and their tokens (Chapter 11)."""
    entries = [json.loads(line) for line in LOG.read_text().splitlines()[start:]] if LOG.exists() else []
    return (
        f"model calls: {len(entries)}; input tokens: {sum(e['input'] for e in entries):,} "
        f"({sum(e['cached'] for e in entries):,} cached); output tokens: {sum(e['output'] for e in entries):,}"
    )


if __name__ == "__main__":
    from agentlab.llm import cost

    month = datetime.now(UTC).strftime("%Y-%m")
    entries = [json.loads(line) for line in LOG.read_text().splitlines()] if LOG.exists() else []
    entries = [entry for entry in entries if entry["time"].startswith(month)]
    print(
        f"{month}: {len(entries)} model calls, "
        f"{sum(e['input'] for e in entries):,} input tokens ({sum(e['cached'] for e in entries):,} cached), "
        f"{sum(e['output'] for e in entries):,} output tokens, "
        f"${sum(cost(e) for e in entries):.4f}"
    )
