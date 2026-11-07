"""Chapter 9 demo: the refiling gate, end to end, as commands run at different times.

    uv run python ch09/refiling_gate.py ask                        # the agent investigates; requests are queued
    uv run python ch09/refiling_gate.py ask --lifetime 5           # requests expire after 5 seconds
    uv run python ch09/refiling_gate.py review                     # what a reviewer sees
    uv run python ch09/refiling_gate.py colleague                  # lab: a colleague replaces the invoice meanwhile
    uv run python ch09/refiling_gate.py decide <request-id> --by lead-031 --approve   # or --reject
    uv run python ch09/refiling_gate.py recover <request-id>       # settle a decision whose outcome is unknown
    uv run python ch09/refiling_gate.py status                     # every request's status and outcome

Lab switch for decide: --crash (the process dies after recording the decision, before sending it).
"""

import argparse
import asyncio
import json
from datetime import datetime, timedelta

from agent_framework import Content

import cobalt
import gate
from investigate import TASK, USER_ID, investigator, run_args, show

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
commands = parser.add_subparsers(dest="command", required=True)
ask_command = commands.add_parser("ask")
ask_command.add_argument("--lifetime", type=float, help="seconds before a request expires (default: 24 hours)")
commands.add_parser("review")
commands.add_parser("colleague")
decide = commands.add_parser("decide")
decide.add_argument("request_id")
decide.add_argument("--by", required=True)
choice = decide.add_mutually_exclusive_group(required=True)
choice.add_argument("--approve", action="store_true")
choice.add_argument("--reject", action="store_true")
decide.add_argument("--crash", action="store_true")
recover = commands.add_parser("recover")
recover.add_argument("request_id")
commands.add_parser("status")
args = parser.parse_args()


async def ask() -> None:
    cobalt.reset(note=True)
    gate.QUEUE.unlink(missing_ok=True)
    agent = investigator()
    session = agent.create_session()
    result = await agent.run(TASK, session=session, function_invocation_kwargs=run_args())
    lifetime = timedelta(seconds=args.lifetime) if args.lifetime else gate.LIFETIME
    for request_id in gate.submit(session, result, requested_by=USER_ID, lifetime=lifetime):
        entry = gate._load()[request_id]
        print(f"{request_id}: {entry['status']}{' (' + entry['reason'] + ')' if entry['reason'] else ''}")
        if entry["status"] == "refused":
            show(await gate.close(investigator(), request_id, "refused", entry["reason"]))


async def review() -> None:
    for request_id in await gate.expire_due(investigator()):  # the sweep a scheduled job would run
        print(f"Closed {request_id}: expired")
    for request_id, entry in gate.pending().items():
        arguments = Content.from_dict(entry["request"]).function_call.parse_arguments()
        waited = gate._now() - datetime.fromisoformat(entry["queued"])
        print(f"Request {request_id}, asked for by {entry['requested_by']}")
        print(f"  Waiting {int(waited.total_seconds() // 60)} min; expires {entry['expires']}")
        print(f"  Approving submits a new filing of {arguments['document_id']} to customs against {arguments['customs_case']}.")
        print(f"  The agent asks for: {entry['call']}")
        print("  The document store reports now:")
        for name, value in gate.facts(arguments).items():
            print(f"    {name}: {value}")
        print("  The agent's reasoning (written by the model, not checked):")
        print("    " + entry["model's reasoning"].replace("\n", "\n    "))


async def decide_one() -> None:
    for request_id in await gate.expire_due(investigator()):  # the sweep a scheduled job would run
        print(f"Closed {request_id}: expired")
    if reason := gate.refusal(args.request_id, args.by):
        print(f"Not sent to the agent: {reason}")
        return
    gate.CRASH_BEFORE_SEND = args.crash
    show(await gate.decide(investigator(), args.request_id, args.by, approved=args.approve))
    print_status(args.request_id)


async def recover_one() -> None:
    result = await gate.recover(investigator(), args.request_id)
    if result:
        show(result)
    print_status(args.request_id)


def print_status(request_id: str | None = None) -> None:
    for rid, entry in gate._load().items():
        if request_id in (None, rid):
            print(f"\nQueue: {rid} is {entry['status']}"
                  f"{'; ' + json.dumps(entry['outcome']) if 'outcome' in entry else ''}"
                  f"{'; ' + entry['reason'] if entry.get('reason') else ''}")
    print(cobalt.where())


if args.command == "ask":
    asyncio.run(ask())
elif args.command == "review":
    asyncio.run(review())
elif args.command == "colleague":
    cobalt.colleague_replaces_invoice()
    print(cobalt.where("DOC-5540"))
    print(cobalt.where("DOC-5531"))
elif args.command == "decide":
    asyncio.run(decide_one())
elif args.command == "recover":
    asyncio.run(recover_one())
else:
    print_status()
