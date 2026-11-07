"""Chapter 15: one investigation read back from its records: the trace as a tree, then the evidence
the agent was given and the case record that carries the same trace ID. No model call.

    uv run python ch15/trace.py TRACE_ID [--store PATH]

The store defaults to the application's own (.cobalt/telemetry). Models are named by their role in
the labs; the spans themselves hold the provider's model IDs.
"""

import argparse
import json
import os
import textwrap
from datetime import datetime
from pathlib import Path

MODEL_ROLES = {"deepseek-flash": "lab model", "deepseek-v4-pro": "larger model"}
SKIP = ("edge_group.process", "workflow.build", "message.send")

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("trace_id")
parser.add_argument(
    "--evidence",
    action="store_true",
    help="print every tool call and what it returned, in full",
)
parser.add_argument(
    "--store",
    default=str(Path(os.environ.get("COBALT_STATE", ".cobalt")) / "telemetry"),
)
args = parser.parse_args()
store = Path(args.store)


def load(kind: str) -> list[dict]:
    path = store / f"{kind}.jsonl"
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def seconds(span: dict) -> float:
    start, end = (
        datetime.fromisoformat(span[k].replace("Z", "+00:00"))
        for k in ("start_time", "end_time")
    )
    return (end - start).total_seconds()


def describe(span: dict) -> str:
    a, name = span["attributes"], span["name"]
    error = (
        f"  ERROR {a.get('error.type', '')}"
        if span["status"]["status_code"] == "ERROR"
        else ""
    )
    if name == "investigate":
        reason = (
            f" ({a['cobalt.flag_reason']})" if a.get("cobalt.flag_reason") else ""
        )
        return f"investigate {a['cobalt.shipment_id']} for {a['enduser.id']}: {a['cobalt.outcome']}{reason}"
    if a.get("gen_ai.operation.name") == "chat":
        model = MODEL_ROLES.get(a.get("gen_ai.request.model", ""), "model")
        return (
            f"chat, {model}: {a.get('gen_ai.usage.input_tokens', 0)} in "
            f"({a.get('gen_ai.usage.cache_read.input_tokens', 0)} cached), {a.get('gen_ai.usage.output_tokens', 0)} out"
        )
    if a.get("gen_ai.operation.name") == "execute_tool":
        return f"tool {a['gen_ai.tool.name']}{error}"
    if a.get("gen_ai.operation.name") == "invoke_agent":
        return f"agent {a.get('gen_ai.agent.name', '')}"
    if name.startswith("read "):
        return f"{name}({', '.join(a.get('cobalt.record_ids', []))}){error}"
    if name.startswith("executor.process"):
        return f"step {a['executor.id']}"
    return name + error


spans = [
    s for s in load("spans") if s["context"]["trace_id"] == "0x" + args.trace_id
]
children: dict = {}
for span in spans:
    children.setdefault(span["parent_id"], []).append(span)


def walk(parent_id, depth: int) -> None:
    for span in sorted(children.get(parent_id, []), key=lambda s: s["start_time"]):
        if span["name"].split(" ")[0] in SKIP:
            walk(span["context"]["span_id"], depth)
            continue
        print(f"{seconds(span):5.2f} s  {'  ' * depth}{describe(span)}"[:85])
        walk(span["context"]["span_id"], depth + 1)


print(f"Trace {args.trace_id}: {len(spans)} spans")
walk(None, 0)
root = next(s for s in spans if s["name"] == "investigate")["attributes"]
print("Configuration on the root span:")
for key, value in root.items():
    if key.startswith("cobalt.") and key.split(".")[1] in (
        "release",
        "instructions",
        "tools",
        "model",
        "request_settings",
        "framework",
        "code",
    ):
        shown = MODEL_ROLES.get(value, value) if key == "cobalt.model" else value
        print(f"  {key.removeprefix('cobalt.'):<24}{shown}")
print(
    f"Cost on the root span: ${root['cobalt.cost_usd']:.5f} (prices of {root['cobalt.price_table']})"
)
evidence = [e for e in load("evidence") if e["trace_id"] == args.trace_id]
for e in evidence:
    calls = [
        c
        for m in e["response"]["messages"]
        for c in m["contents"]
        if c["type"] == "function_call"
    ]
    print(
        f"Evidence: the case file for {e['case_file']['shipment_id']}, the task, and {len(calls)} tool call(s):"
    )
    for c in calls:
        print(
            f"  {c['name']}({c['arguments'][:60]}{'...' if len(c['arguments']) > 60 else ''})"
        )
    if args.evidence:
        for m in e["response"]["messages"]:
            for c in m["contents"]:
                if c["type"] in ("function_call", "function_result"):
                    text = (
                        c.get("arguments")
                        if c["type"] == "function_call"
                        else str(c.get("result"))
                    )
                    label = (
                        f"{c['name']} called with"
                        if c["type"] == "function_call"
                        else "returned"
                    )
                    print(
                        textwrap.fill(
                            f"{label}: {text}", 85, subsequent_indent="    "
                        )
                    )
cases = store.parent / "cases.json"
for case in (json.loads(cases.read_text()) if cases.exists() else {}).values():
    moves = [e for e in case["events"] if e.get("trace_id") == args.trace_id]
    if moves:
        print(f"Case record {case['case_id']}, moves carrying this trace ID:")
        for e in moves:
            print(f"  {e['from']} -> {e['to']} by {e['by']}")
