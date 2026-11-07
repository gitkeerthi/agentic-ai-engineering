"""Chapter 14 demo, no model: reconstruct one investigation from the trace ID on its case record.

    uv run python ch14/reconstruct.py TRACE_ID [--store NAME] [--evidence]

Prints the case record, the configuration the run used and whether an evaluation approved it, the trace, and
where the run's time and money went. --evidence adds what the agent was sent and every report it made, from
the evidence store, a separate store with its own access rules.
"""

import argparse
import json
import textwrap

from show import HERE, case_line, load, print_trace, role, seconds, spans_of

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("trace_id")
parser.add_argument("--store", default="week")
parser.add_argument(
    "--evidence", action="store_true", help="also read the evidence store"
)
args = parser.parse_args()

store = HERE / "store" / args.store
[record] = [r for r in load(store, "cases") if r["trace_id"] == args.trace_id]
print(case_line(record))

EVALUATED = json.loads((HERE / "evaluated.json").read_text())["configurations"]


def compare(a: dict) -> list[str]:
    """Each part of the run's configuration against the evaluated configuration
    with the same instructions, if there is one."""
    md5 = a["cobalt.instructions.md5"]
    match = next((c for c in EVALUATED if c["instructions.md5"] == md5), None)
    if match is None:
        return [f"  instructions {md5[:8]}  never evaluated"]
    version = f"version {match['version']}, evaluated, {match['decision']}"
    lines = [f"  instructions {md5[:8]}  {version}"]
    for part in ("model", "framework.version"):
        value = a[f"cobalt.{part}"]
        verdict = "as evaluated" if value == match[part] else "NOT as evaluated"
        shown = role(value) if part == "model" else value
        lines.append(f"  {part.split('.')[0]:<12} {shown}  {verdict}")
    for part in ("tools", "code", "client"):  # parts the evaluation didn't record
        lines.append(f"  {part:<12} {a[f'cobalt.{part}.md5'][:8]}  not recorded then")
    return lines


spans = spans_of(store, args.trace_id)
roots = [s for s in spans if s["name"] == "investigate"]
if not roots:  # an ID of the run's own, or a trace the sampler didn't keep
    print("\nNo trace for this ID: tracing was off, or the trace wasn't kept.")
else:
    root = roots[0]
    a = root["attributes"]
    service = root["resource"]["attributes"]["service.name"]
    print(f"\nConfiguration (release {a['cobalt.release']}, {service}):")
    print("\n".join(compare(a)))
    print()
    print_trace(store, args.trace_id)
    chats = [s for s in spans if s["attributes"].get("gen_ai.operation.name") == "chat"]
    model_time = sum(seconds(s) for s in chats)
    print(
        f"\nTime: {seconds(root):.2f} s, of which {model_time:.2f} s "
        f"in {len(chats)} model call(s)"
    )
    print(
        f"Tokens: {a['cobalt.usage.input_tokens']} in "
        f"({a['cobalt.usage.cached_input_tokens']} cached), "
        f"{a['cobalt.usage.output_tokens']} out; cost ${float(a['cobalt.cost_usd']):.6f} "
        f"(prices of {a['cobalt.price_table']})"
    )

if args.evidence:
    found = [e for e in load(store, "evidence") if e["trace_id"] == args.trace_id]
    if not found:
        print("\nNo evidence: the run ended before the agent ran.")
        raise SystemExit
    evidence = found[0]
    print("\nEvidence: the agent was sent")
    for key, value in json.loads(evidence["sent"]).items():
        line = f"{key}: {json.dumps(value)}"
        print(textwrap.fill(line, 86, initial_indent="  ", subsequent_indent="      "))
    if evidence["response"] is None:
        print("\nThe agent's run raised: no response was kept.")
        raise SystemExit
    contents = [c for m in evidence["response"]["messages"] for c in m["contents"]]
    results = {c["call_id"]: c.get("result") for c in contents if c["type"] == "function_result"}
    for c in contents:
        if c["type"] == "function_call":
            answered = results.get(c["call_id"])
            print(f"\nReport, call ...{c['call_id'][-4:]}, answered {answered!r}:")
            print(textwrap.fill(c["arguments"], 86, initial_indent="  ", subsequent_indent="  "))
