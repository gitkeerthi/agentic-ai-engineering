"""Chapter 14 experiment: attach each run's result against the golden set to its trace in Langfuse, as a score.
The evaluation's verdict joins the trace on the trace ID, the same ID the case record carries.

    uv run python ch14/scores.py STORE

The score, `golden`, is one of: right (the run's typed output matches the case's known answer, whether that is a
finding or a flag for a person), wrong (a finding released that doesn't match), flagged (sent to a person, though
the known answer was something else) or failed. Sending a store's scores again replaces them: each has a fixed ID.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from langfuse.api import CreateScoreRequest

from golden import right
from to_langfuse import client

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("store")
args = parser.parse_args()

cases = Path(__file__).parent / "store" / args.store / "cases.jsonl"
records = [json.loads(line) for line in cases.read_text().splitlines()]


def verdict(record: dict) -> str:
    if right(record["shipment_id"], record["output"]):
        return "right"
    return {"finding": "wrong", "flagged": "flagged", "failed": "failed"}[record["outcome"]]


verdicts = [verdict(record) for record in records]
client().api.scores.create(  # one request for the whole store
    request=[
        CreateScoreRequest(
            id=f"{record['trace_id']}-golden",  # the same ID again replaces it
            trace_id=record["trace_id"],
            name="golden",
            value=value,
            data_type="CATEGORICAL",
        )
        for record, value in zip(records, verdicts)
    ]
)
tally = Counter(verdicts)
print(f"Scored {len(records)} traces:", ", ".join(f"{n} {v}" for v, n in tally.most_common()))
