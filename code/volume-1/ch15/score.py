"""Chapter 15: score a saved evaluation batch. No model call.

    uv run python ch15/score.py STORE [--baseline ../ch14/store/week] [--release]

Per case: right runs with a 95% Wilson interval, and released wrong findings (the must-pass count).
Then the batch's configuration, model calls, tokens and cost per run and per right finding.
--baseline scores Chapter 14's saved week batch on the cases both sets share, on the fields both
contracts have. --release writes cobalt_exceptions/evaluated.json, but only if every run used one
configuration and no wrong finding was released.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import binomtest

from golden import BY_SHIPMENT, CASES, released_wrong, right

HERE = Path(__file__).parent
MODEL_ROLES = {
    "deepseek-flash": "lab model",
    "deepseek-v4-pro": "larger model",
}  # printouts name the role
parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("store")
parser.add_argument("--baseline")
parser.add_argument("--release", action="store_true")
args = parser.parse_args()
store = HERE / "store" / args.store
runs = [json.loads(line) for line in (store / "runs.jsonl").read_text().splitlines()]
calls = Counter(
    json.loads(line)["context"]["trace_id"][2:]
    for line in (store / "spans.jsonl").read_text().splitlines()
    if json.loads(line)["name"].startswith("chat ")
)


def interval(k: int, n: int) -> str:
    low, high = binomtest(k, n).proportion_ci(method="wilson")
    return f"{low:4.0%} to {high:4.0%}"


by_case = defaultdict(list)
for run in runs:
    by_case[run["shipment_id"]].append(run)

print(
    f"{'case':<9}{'split':<12}{'right':>7}  {'95% interval':<14}{'released wrong':>15}"
)
for case in CASES:
    mine = by_case[case["shipment_id"]]
    k = sum(right(case["shipment_id"], r["output"]) for r in mine)
    wrong = sum(released_wrong(case["shipment_id"], r["output"]) for r in mine)
    shown = interval(k, len(mine)) if len(mine) > 1 else "(no model)"
    print(
        f"{case['shipment_id']:<9}{case['split']:<12}{k:>3}/{len(mine):<3}  {shown:<14}{wrong:>15}"
    )

agent_runs = [r for r in runs if calls[r["trace_id"]]]
right_releases = sum(
    r["outcome"] == "finding" and right(r["shipment_id"], r["output"]) for r in runs
)
wrong_releases = sum(released_wrong(r["shipment_id"], r["output"]) for r in runs)
total = sum(r["cost_usd"] for r in runs)
tokens = Counter()
for r in runs:
    tokens.update({k: v for k, v in r["usage"].items() if isinstance(v, int)})
print(
    f"\nRuns: {len(runs)} ({len(agent_runs)} reached the agent); model calls: {sum(calls.values())}"
)
print(
    f"Right: {sum(right(r['shipment_id'], r['output']) for r in runs)} of {len(runs)}; released: {sum(r['outcome'] == 'finding' for r in runs)}, of which wrong: {wrong_releases}"
)
print(
    f"Tokens: {tokens['input_token_count']:,} in ({tokens['cache_read_input_token_count']:,} cached), {tokens['output_token_count']:,} out"
)
print(
    f"Cost: ${total:.4f}; per agent run ${total / max(len(agent_runs), 1):.5f}; per right finding released ${total / max(right_releases, 1):.5f}"
)
print(
    f"Model calls per agent run: {dict(sorted(Counter(calls[r['trace_id']] for r in agent_runs).items()))}"
)

configs = {json.dumps(r["configuration"], sort_keys=True) for r in runs}
print(f"Configurations: {len(configs)}")
for part, value in json.loads(next(iter(configs))).items():
    print(f"  {part.removeprefix('cobalt.'):<22}{MODEL_ROLES.get(value, value)}")

if args.baseline:
    shared = (
        "ending",
        "reason",
        "status",
        "refiling",
    )  # fields Chapter 14's contract also has
    base = [
        json.loads(line)
        for line in (HERE / args.baseline / "cases.jsonl").read_text().splitlines()
    ]
    print(
        f"\nOn the {len({r['shipment_id'] for r in base})} cases Chapter 14's batch ran, scored on {', '.join(shared)}:"
    )
    print(f"{'case':<9}{'Chapter 14':>12}{'Chapter 15':>12}")
    totals = [[0, 0, 0], [0, 0, 0]]
    for sid in sorted(
        {r["shipment_id"] for r in base},
        key=lambda s: [c["shipment_id"] for c in CASES].index(s),
    ):
        row = []
        for i, batch in enumerate((base, runs)):
            mine = [r for r in batch if r["shipment_id"] == sid]
            k = sum(right(sid, r["output"], shared) for r in mine)
            w = sum(
                r["outcome"] == "finding" and not right(sid, r["output"], shared)
                for r in mine
            )
            totals[i][0] += k
            totals[i][1] += len(mine)
            totals[i][2] += w
            row.append(f"{k}/{len(mine)}")
        print(f"{sid:<9}{row[0]:>12}{row[1]:>12}")
    for name, (k, n, w) in zip(("Chapter 14", "Chapter 15"), totals):
        print(f"{name}: right {k} of {n}; released wrong {w}")

if args.release:
    if len(configs) != 1 or wrong_releases:
        raise SystemExit(
            "not recorded: the batch used more than one configuration or released a wrong finding"
        )
    evaluated = {
        "golden_set": json.loads((HERE / "golden.json").read_text())["version"],
        "store": f"ch15/store/{args.store}",
        "runs": len(runs),
        "released_wrong": wrong_releases,
        "configuration": json.loads(next(iter(configs))),
    }
    target = HERE.parent / "cobalt_exceptions" / "evaluated.json"
    target.write_text(json.dumps(evaluated, indent=2) + "\n")
    print(
        f"\nRecorded the evaluated configuration in {target.relative_to(HERE.parent)}"
    )
