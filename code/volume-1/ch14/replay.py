"""Chapter 14 experiment: resend a recorded request several times and count what the agent reports.

Rerunning a case rebuilds the request from today's records and configuration. A replay restores the recorded
instructions and case file, then compares the recorded tools, code, client settings, model name, and framework
version with today's. Missing historical values cannot be checked; changed values stop the replay unless
--anyway is supplied. Even when recorded dependencies match, the provider may change the model behind its name.

    uv run python ch14/replay.py TRACE_ID [N] [--store NAME]
    uv run python ch14/replay.py ch13:VERSION:SHIPMENT_ID:RUN [N]

The second form replays a run saved by Chapter 13's evaluation, which recorded the instructions' hash and the
case file the agent was sent, but not the tools, code, or client settings.
"""

import argparse
import asyncio
import hashlib
import json
import textwrap
from collections import Counter

from agentlab.llm import MODEL, make_client
from agentlab.usage import mark, since
from show import HERE, load, spans_of
from steps import interpreter, reported_finding
from telemetry import configuration
from versions import VERSIONS

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("source")
parser.add_argument("n", nargs="?", type=int, default=10)
parser.add_argument("--store", default="week")
parser.add_argument("--anyway", action="store_true", help="replay even if a part changed")
args = parser.parse_args()

if args.source.startswith("ch13:"):
    _, version, shipment_id, run = args.source.split(":")
    saved = (
        (HERE.parent / "ch13" / "results" / f"{version}.jsonl")
        .read_text()
        .splitlines()
    )
    [recorded] = [
        r
        for r in map(json.loads, saved)
        if (r["shipment_id"], r["run"]) == (shipment_id, int(run))
    ]
    instructions_md5, sent = recorded["instructions_md5"], recorded["query"]
    then = {"cobalt.model": recorded["model"], "cobalt.framework.version": recorded["framework"]}
else:
    [recorded] = [
        e
        for e in load(HERE / "store" / args.store, "evidence")
        if e["trace_id"] == args.source
    ]
    instructions_md5, sent = recorded["instructions_md5"], recorded["sent"]
    spans = spans_of(HERE / "store" / args.store, args.source)
    roots = [s["attributes"] for s in spans if s["name"] == "investigate"]
    then = roots[0] if roots else {}  # no trace kept: every part "not recorded"

by_hash = {
    hashlib.md5(text.encode()).hexdigest(): name for name, text in VERSIONS.items()
}
if instructions_md5 not in by_hash:
    raise SystemExit(f"No instructions with hash {instructions_md5}: can't replay.")
model = then.get("cobalt.model", MODEL)  # the recorded model's name, if recorded
agent = interpreter(make_client(model=model), VERSIONS[by_hash[instructions_md5]])
print(f"Replaying {args.source}: instructions version {by_hash[instructions_md5]}")
now = configuration(agent)
for key in ("cobalt.tools.md5", "cobalt.code.md5", "cobalt.client.md5", "cobalt.model",
            "cobalt.framework.version"):  # the parts a replay takes from today
    verdict = "not recorded" if key not in then else "same" if then[key] == now[key] else "CHANGED"
    print(f"  {key.removeprefix('cobalt.'):<18} {verdict}")
    if verdict == "CHANGED" and not args.anyway:  # not the recorded request any more
        raise SystemExit(f"{key} has changed since the run; --anyway replays regardless")


async def main() -> None:
    start, counts = mark(), Counter()
    for attempt in range(1, args.n + 1):
        finding = reported_finding(await agent.run(sent))
        status = finding.status if finding else "no valid report"
        counts[status] += 1
        print(f"  {attempt:>2}. {status}")
        if finding and finding.cause:  # printed whole, so that a reader can judge it
            print(
                textwrap.fill(
                    finding.cause,
                    84,
                    initial_indent="      ",
                    subsequent_indent="      ",
                )
            )
    print(
        "Totals: "
        + ", ".join(
            f"{status} {n} of {args.n}" for status, n in counts.most_common()
        )
    )
    print(f"Cost: {since(start)}")


asyncio.run(main())
