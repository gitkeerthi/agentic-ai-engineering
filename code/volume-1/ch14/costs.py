"""Chapter 14 experiment, no model: tokens, latency and cost per run, per case and per successful run, read from
the stores a batch left (week.py), or from Chapter 13's saved evaluation runs.

    uv run python ch14/costs.py STORE [STORE ...]
    uv run python ch14/costs.py --ch13 A B

Costs are at list prices (the provider's peak rate), so that batches run at different hours compare; the
usage log keeps what each call was billed. A success is counted two ways: a released finding (what production
can count) and a released finding that matches the case's known answer (what only an evaluation can count).
"""

import argparse
import json
import statistics
from collections import defaultdict

from agentlab.llm import PRICES
from golden import BY_SHIPMENT, CASES, right
from show import HERE, load, role, seconds


def list_price(model: str, tokens_in: int, cached: int, tokens_out: int) -> float:
    """What the tokens cost at the peak rate, cached input at its own price."""
    p = PRICES[model]
    return (
        (tokens_in - cached) * p["input"][0]
        + cached * p["cached_input"][0]
        + tokens_out * p["output"][0]
    ) / 1e6


def tokens(chats: list[dict], key: str) -> int:
    return sum(int(c["attributes"].get(key, 0)) for c in chats)


def from_store(name: str) -> list[dict]:
    """One row per run: its root span's usage and outcome, its model time, and its case record."""
    store = HERE / "store" / name
    cases = {r["trace_id"]: r for r in load(store, "cases")}
    spans = defaultdict(list)
    for span in load(store, "spans"):
        spans[span["context"]["trace_id"][2:]].append(span)
    rows = []
    for trace_id, record in cases.items():
        [root] = [s for s in spans[trace_id] if s["name"] == "investigate"]
        chats = [
            s
            for s in spans[trace_id]
            if s["attributes"].get("gen_ai.operation.name") == "chat"
        ]
        a = root["attributes"]
        rows.append(
            {
                "shipment_id": record["shipment_id"],
                "model": a["cobalt.model"],
                "version": a["cobalt.instructions.md5"],
                "calls": len(chats),
                # summed from the model calls, which count even when a run raised
                "in": tokens(chats, "gen_ai.usage.input_tokens"),
                "cached": tokens(chats, "gen_ai.usage.cache_read.input_tokens"),
                "out": tokens(chats, "gen_ai.usage.output_tokens"),
                "seconds": seconds(root),
                "model_seconds": sum(seconds(s) for s in chats),
                "released": record["outcome"] == "finding",
                "right": record["outcome"] == "finding"
                and right(record["shipment_id"], record["output"]),
            }
        )
    return rows


def from_ch13(version: str) -> list[dict]:
    """The same rows from Chapter 13's saved runs, which kept each run's usage but not its timing."""
    saved = (
        (HERE.parent / "ch13" / "results" / f"{version}.jsonl")
        .read_text()
        .splitlines()
    )
    rows = []
    for run in map(json.loads, saved):
        usage = (run["response"] or {}).get("usage_details") or {}
        released = run["answer"]["ending"] == "finding"
        rows.append(
            {
                "shipment_id": run["shipment_id"],
                "model": run["model"],
                "version": run["instructions_md5"],
                "calls": run["model_calls"],
                "in": usage.get("input_token_count", 0),
                "cached": usage.get("cache_read_input_token_count", 0),
                "out": usage.get("output_token_count", 0),
                "seconds": None,
                "released": released,
                "right": released and not run["misses"],
            }
        )
    return rows


def report(label: str, rows: list[dict]) -> None:
    costs = [list_price(r["model"], r["in"], r["cached"], r["out"]) for r in rows]
    total = sum(costs)
    calls = sum(r["calls"] for r in rows)
    print(
        f"{label}: {len(rows)} runs on the {role(rows[0]['model'])}, {calls} model calls, "
        f"${total:.4f} at list prices"
    )
    print(
        f"  per run: {statistics.mean(r['in'] for r in rows):,.0f} tokens in "
        f"({statistics.mean(r['cached'] for r in rows):,.0f} cached), "
        f"{statistics.mean(r['out'] for r in rows):,.0f} out, ${total / len(rows):.5f}"
    )
    timed = [r for r in rows if r["seconds"] is not None and r["calls"]]
    if timed:
        times = sorted(r["seconds"] for r in timed)
        share = sum(r["model_seconds"] for r in timed) / sum(times)
        print(
            f"  agent runs: median {statistics.median(times):.2f} s, "
            f"slowest {times[-1]:.2f} s; {share:.1%} of the time in model calls"
        )
        for n in sorted({r["calls"] for r in timed}):  # time grows with model calls
            group = [r["seconds"] for r in timed if r["calls"] == n]
            print(
                f"    {len(group):>3} runs with {n} model call(s): "
                f"median {statistics.median(group):.2f} s"
            )
    released = sum(r["released"] for r in rows)
    correct = sum(r["right"] for r in rows)
    print(
        f"  released findings: {released}, ${total / released:.5f} each; "
        f"released and right: {correct}, ${total / correct:.5f} each"
    )
    print(
        f"  {'case':<9} {'runs':>4} {'calls':>5} {'released':>8} {'right':>5} "
        f"{'median s':>8} {'cost/run':>9}"
    )
    for case in CASES:
        mine = [
            (r, c)
            for r, c in zip(rows, costs)
            if r["shipment_id"] == case["shipment_id"]
        ]
        if not mine:
            continue
        timed = [r["seconds"] for r, _ in mine if r["seconds"] is not None]
        print(
            f"  {case['shipment_id']:<9} {len(mine):>4} {sum(r['calls'] for r, _ in mine):>5} "
            f"{sum(r['released'] for r, _ in mine):>8} {sum(r['right'] for r, _ in mine):>5} "
            f"{(f'{statistics.median(timed):.2f}' if timed else '-'):>8} "
            f"${statistics.mean(c for _, c in mine):.5f}"
        )
    print()


parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument(
    "names", nargs="+", help="stores in ch14/store/, or versions with --ch13"
)
parser.add_argument(
    "--ch13",
    action="store_true",
    help="read Chapter 13's saved runs of these versions",
)
args = parser.parse_args()

assert set(BY_SHIPMENT) == {c["shipment_id"] for c in CASES}
for name in args.names:
    report(
        f"Chapter 13, version {name}" if args.ch13 else f"Store {name}",
        from_ch13(name) if args.ch13 else from_store(name),
    )
