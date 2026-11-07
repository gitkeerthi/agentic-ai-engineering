"""Reading the stores back: the spans of one trace, printed as a tree, and one-line forms of the other records.

The printouts name models by their role in the labs; the spans themselves hold the provider's model IDs.
"""

import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
MODEL_ROLES = {"deepseek-flash": "lab model", "deepseek-v4-pro": "larger model"}
WIDTH = 86


def load(store: Path, kind: str) -> list[dict]:
    path = store / f"{kind}.jsonl"
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def spans_of(store: Path, trace_id: str) -> list[dict]:
    return [
        s
        for s in load(store, "spans")
        if s["context"]["trace_id"] == "0x" + trace_id
    ]


def seconds(span: dict) -> float:
    start, end = (
        datetime.fromisoformat(span[k].replace("Z", "+00:00"))
        for k in ("start_time", "end_time")
    )
    return (end - start).total_seconds()


def role(model: str) -> str:
    return MODEL_ROLES.get(model, model)


def describe(span: dict) -> str:
    """One span's line: what it was and the attributes that matter for diagnosis."""
    a = span["attributes"]
    name = span["name"]
    operation = a.get("gen_ai.operation.name")
    failed = span["status"]["status_code"] == "ERROR"
    error = f"  ERROR {a.get('error.type', '')}".rstrip() if failed else ""
    if name == "investigate":
        status = a.get("cobalt.status") or a.get("error.type", "")
        reason = (
            f" ({a['cobalt.flag_reason']})" if a.get("cobalt.flag_reason") else ""
        )
        return f"investigate {a['cobalt.shipment_id']}: {a['cobalt.outcome']}{reason}, {status}"
    if operation == "chat":
        finish = ", ".join(
            json.loads(a.get("gen_ai.response.finish_reasons", "[]"))
        )
        return (
            f"chat {role(a.get('gen_ai.response.model') or a.get('gen_ai.request.model', ''))}: {a.get('gen_ai.usage.input_tokens', 0)} in"
            f" ({a.get('gen_ai.usage.cache_read.input_tokens', 0)} cached),"
            f" {a.get('gen_ai.usage.output_tokens', 0)} out, {finish}"
        )
    if operation == "execute_tool":
        return f"execute_tool {a['gen_ai.tool.name']}, call ...{a.get('gen_ai.tool.call.id', '')[-4:]}{error}"
    if operation == "invoke_agent":
        return f"invoke_agent {a.get('gen_ai.agent.name', '')}"
    if name.startswith("read "):
        return f"{name}({', '.join(a.get('cobalt.record_ids', []))}){error}"
    if name.startswith(("memory ", "context ")):
        count = a.get("cobalt.messages", a.get("cobalt.messages_added"))
        ids = (
            f", records {', '.join(a['cobalt.record_ids'])}"
            if a.get("cobalt.record_ids")
            else ""
        )
        return f"{name}: {count} message(s){ids}"
    if name.startswith("executor.process"):
        return f"step {a['executor.id']}"
    if name == "message.send":
        return f"send {a.get('message.type', '')}"
    return name + error


def print_trace(
    store: Path, trace_id: str, skip=("edge_group.process", "workflow.build")
) -> None:
    """The trace as a tree: each span's duration and its line, children in the order they started."""
    spans = spans_of(store, trace_id)
    service = (
        spans
        and min(spans, key=lambda s: s["start_time"])["resource"]["attributes"][
            "service.name"
        ]
    )
    by_parent: dict = {}
    for span in spans:
        by_parent.setdefault(span["parent_id"], []).append(span)

    def walk(parent_id, depth):
        for span in sorted(
            by_parent.get(parent_id, []), key=lambda s: s["start_time"]
        ):
            if span["name"].split(" ")[0] in skip:
                walk(
                    span["context"]["span_id"], depth
                )  # keep its children, at the same depth
                continue
            other = span["resource"]["attributes"]["service.name"]
            elsewhere = (
                f"  [{other}]" if other != service else ""
            )  # a span another service recorded
            print(
                f"{seconds(span):5.2f} s  {'  ' * depth}{describe(span)}{elsewhere}"[
                    :WIDTH
                ]
            )
            walk(span["context"]["span_id"], depth + 1)

    print(f"Trace {trace_id}: {len(spans)} spans")
    walk(None, 0)


def case_line(record: dict) -> str:
    """The case system's record, in one line."""
    output = record["output"] or {}
    finding = output.get("finding", output) if "reason" in output else output
    reason = f" ({output['reason']})" if "reason" in output else ""
    status = finding.get("status") if finding else None
    return (
        f"Case record: {record['shipment_id']} {record['outcome']}{reason}, {status}\n"
        f"  release {record['release']}, trace {record['trace_id']}"
    )
