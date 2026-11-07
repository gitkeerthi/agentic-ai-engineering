"""Chapter 14 demo, no model: what the trace and the logs hold of one investigation, with sensitive data off
(the default, and production's setting) or on.

    uv run python ch14/what_a_trace_holds.py [--sensitive]

The agent replies from a script, so the run is the same every time and costs nothing. Prints each kind of span
with the attributes it carries, then searches every span and log record for text from the case file the agent
was sent and from the finding it reported.
"""

import argparse
import asyncio
import json
import shutil
import textwrap

import telemetry
from scripted import ScriptedClient
from show import load
from steps import interpreter, investigation

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument(
    "--sensitive",
    action="store_true",
    help="turn sensitive data on, as in development",
)
args = parser.parse_args()

name = "holds-on" if args.sensitive else "holds-off"
shutil.rmtree(telemetry.HERE / "store" / name, ignore_errors=True)
store = telemetry.setup(name, sensitive=args.sensitive)

FINDING = {
    "shipment_id": "SH-4471",
    "status": "cause_found",
    "cause": "The commercial invoice is filed against customs case RTM-88124 instead of RTM-88213.",
    "evidence": [{"record_id": "DOC-5531", "fact": "Filed against RTM-88124."}],
    "recommended_action": "Refile DOC-5531 against RTM-88213.",
    "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"},
}
usage = {
    "input_token_count": 1305,
    "cache_read_input_token_count": 1152,
    "output_token_count": 340,
}
client = ScriptedClient([("report_finding", FINDING, "call_1")], usage=usage)
agent = interpreter(client=client, middleware=[telemetry.keep_evidence])
asyncio.run(telemetry.investigate(investigation(agent), agent, "SH-4471"))
telemetry.close()

spans, logs = load(store, "spans"), load(store, "logs")
print(
    f"Sensitive data {'on' if args.sensitive else 'off'}: {len(spans)} spans, {len(logs)} log records\n"
)
kinds: dict = {}
for span in spans:
    kind = (
        span["attributes"].get("gen_ai.operation.name")
        or span["name"].split(" ")[0]
    )
    kinds.setdefault(kind, set()).update(span["attributes"])
for kind in ("investigate", "invoke_agent", "chat", "execute_tool"):
    print(f"{kind}:")
    print(
        textwrap.fill(
            ", ".join(sorted(kinds[kind])),
            84,
            initial_indent="    ",
            subsequent_indent="    ",
        )
    )

SECRETS = {  # text that is in the case file or the finding, and nowhere else
    "case file: location": "Rotterdam customs yard",
    "case file: contents": "industrial pumps",
    "instructions": "You interpret the records",
    "finding: cause": "instead of RTM-88213",
}
print("\nWhere the run's content appears:")
for label, text in SECRETS.items():
    holders = sorted(
        {
            s["attributes"].get("gen_ai.operation.name") or s["name"]
            for s in spans
            if text in json.dumps(s)
        }
        | ({"log records"} if any(text in json.dumps(r) for r in logs) else set())
    )
    print(f"    {label:<22} {', '.join(holders) or 'nowhere'}")
evidence = load(store, "evidence")
print(
    f"\nEvidence store: {len(evidence)} record, {len(json.dumps(evidence[0]))} characters, "
    f"holds the case file: {SECRETS['case file: location'] in evidence[0]['sent']}"
)
