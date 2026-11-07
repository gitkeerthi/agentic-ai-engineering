"""Chapter 14 demo: what Langfuse holds for runs that week.py --langfuse sent it, read back through its public
API. Prints one run's observations as Langfuse typed them, then Langfuse's own totals for the stores' runs: cost
and latency by model, scores, runs, model calls and cost by session (one case each), traces by their root, and
tokens by observation type, beside the totals our trace store's root spans record.

    uv run python ch14/in_langfuse.py STORE [STORE ...] [--trace TRACE_ID]

The run shown is the first in the first store, unless --trace names another.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from show import role
from to_langfuse import client

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("stores", nargs="+")
parser.add_argument("--trace")
args = parser.parse_args()

langfuse = client().api
STORE = Path(__file__).parent / "store"
records = [
    json.loads(line)
    for name in args.stores
    for line in (STORE / name / "cases.jsonl").read_text().splitlines()
]
spans = [
    json.loads(line)
    for name in args.stores
    for line in (STORE / name / "spans.jsonl").read_text().splitlines()
]
roots = [span for span in spans if span["name"] == "investigate"]
started = {span["context"]["span_id"][2:]: span["start_time"] for span in spans}


def observations(**query) -> list[dict]:
    page = langfuse.observations.get_many(
        fields="core,basic,model,usage,metrics,trace_context", limit=1000, **query
    )
    return [o.dict(by_alias=True) for o in page.data]


def metrics(view: str, dimension, measures: list[tuple], **filters) -> list[dict]:
    """Langfuse's aggregation over the stores' time range, grouped by one dimension
    (or none)."""
    times = sorted(datetime.fromisoformat(r["time"]) for r in records)
    query = {
        "view": view,
        "dimensions": [{"field": dimension}] if dimension else [],
        "metrics": [{"measure": m, "aggregation": a} for m, a in measures],
        "filters": [
            {"column": c, "operator": "=", "value": v, "type": t}
            for c, (v, t) in filters.items()
        ],
        "fromTimestamp": (times[0] - timedelta(minutes=5)).isoformat(),
        "toTimestamp": (times[-1] + timedelta(minutes=5)).isoformat(),
    }
    return langfuse.metrics.metrics(query=json.dumps(query)).data


# One run, as Langfuse holds it
PLUMBING = ("edge_group.process", "message.send")  # the workflow passing messages
trace_id = args.trace or records[0]["trace_id"]
# Langfuse keeps times to the millisecond; our store's start times put steps that
# began in the same millisecond in the order they ran
run = sorted(observations(trace_id=trace_id), key=lambda o: started[o["id"]])
children: dict = {}
for o in run:
    children.setdefault(o.get("parentObservationId"), []).append(o)
[root] = [o for o in run if o["isRootObservation"]]
hidden = sum(o["name"].startswith(PLUMBING) for o in run)


def show(o: dict, depth: int) -> None:
    if o["name"].startswith(PLUMBING):
        depth -= 1  # not shown, but its children are
    else:
        line = f"{'  ' * depth}{o['type']:<10} {o['name']}"
        if o["type"] == "GENERATION":
            usage = o["usageDetails"]
            line = line.replace(o["model"], role(o["model"]))
            line += (f": input {usage.get('input', 0)} + "
                     f"{usage.get('input_cached_tokens', 0)} cached, output "
                     f"{usage.get('output', 0)}, ${o['totalCost']:.6f}")
        if o.get("latency") is not None:
            line += f", {o['latency']:.2f} s"
        print(line)
    for child in children.get(o["id"], []):
        show(child, depth + 1)


print(f"Trace {trace_id}: session {root['sessionId']}, version {root['version']}, "
      f"environment {root['environment']}")
show(root, 0)
print(f"({hidden} of {len(run)} observations not shown: {', '.join(PLUMBING)})")

# Langfuse's totals for the stores' runs, by model
print()
print("Langfuse, model calls by model:")
by_model = metrics(
    "observations",
    "providedModelName",
    [("count", "count"), ("totalCost", "sum"), ("latency", "p50"), ("latency", "max")],
    type=("GENERATION", "string"),
)
for row in by_model:
    print(f"  {role(row['providedModelName']):<13} {row['count_count']:>3} calls  "
          f"${row['sum_totalCost']:.4f}  median {row['p50_latency'] / 1000:.2f} s, "
          f"slowest {row['max_latency'] / 1000:.2f} s")
print(f"  {'all':<13} {sum(r['count_count'] for r in by_model):>3} calls  "
      f"${sum(r['sum_totalCost'] for r in by_model):.4f}")
print("Langfuse, runs scored against the golden set:")
for row in metrics("scores-categorical", "stringValue", [("count", "count")],
                   name=("golden", "string")):
    print(f"  {row['stringValue']:<8} {row['count_count']:>4}")

wrong = langfuse.scores.get_many(
    name="golden", data_type="CATEGORICAL", value="wrong", fields="subject", limit=100
)
for score in wrong.data:
    print(f"    wrong: {score.subject.kind} {score.subject.id}")
print("Langfuse, by session:")
for case in dict.fromkeys(r["shipment_id"] for r in records):  # in the stores' order
    session = {"sessionId": (case, "string")}
    [runs] = metrics("observations", None, [("count", "count")],
                     isRootObservation=(True, "boolean"), **session)
    calls = metrics("observations", None, [("count", "count"), ("totalCost", "sum")],
                    type=("GENERATION", "string"), **session)
    count, total = (calls[0]["count_count"], calls[0]["sum_totalCost"]) if calls else (0, 0)
    print(f"  {case}  {runs['count_count']:>2} runs  {count:>2} model calls  ${total or 0:.4f}")

print("Langfuse, traces by root observation:")
for row in metrics("observations", "name", [("count", "count")], isRootObservation=(True, "boolean")):
    print(f"  {row['name']:<15} {row['count_count']:>4}")
print("Langfuse, tokens by observation type:")
for row in metrics("observations", "type", [("inputTokens", "sum"), ("outputTokens", "sum")]):
    print(f"  {row['type']:<11} input {row['sum_inputTokens']:>7,}  output {row['sum_outputTokens']:>6,}")


def total(key: str):
    return sum(span["attributes"][key] for span in roots)


print(f"Our trace store: {len(roots)} runs, ${total('cobalt.cost_usd'):.4f}, input "
      f"{total('cobalt.usage.input_tokens'):,}, output {total('cobalt.usage.output_tokens'):,} "
      "(root spans)")
