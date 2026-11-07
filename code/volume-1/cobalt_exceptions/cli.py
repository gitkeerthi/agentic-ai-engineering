"""The application's entry points, as one command with subcommands.

    cobalt reset                                    put every stand-in record back
    cobalt investigate SH-4471 --as analyst-017     open a case and investigate
    cobalt review                                   pending refilings, with what the store says now
    cobalt decide REQ-0001 --as lead-031 --approve  (or --reject)
    cobalt recover REQ-0001                         settle a filing whose reply was lost
    cobalt customs                                  lab: customs processes filings; filed cases are checked
    cobalt expire                                   close requests nobody answered in time
    cobalt status [SH-4471]                         a case and every move it made

Every command reads and writes the stand-in systems in the state folder (COBALT_STATE, default
.cobalt/), so each can run in its own process, as the people involved would run them.
"""

import argparse
import asyncio
import json
import textwrap
from pathlib import Path

from .domain.contracts import Finding, Flagged, InvestigationRequest
from .services import casework, gate
from .systems import approvals, cases, records, storage

EVALUATED = (
    Path(__file__).parent / "evaluated.json"
)  # written by the release's evaluation


def say(text: str, indent: str = "") -> None:
    """Print one line, wrapped to fit a terminal or a page."""
    print(
        textwrap.fill(
            text, 85, initial_indent=indent, subsequent_indent=indent + "    "
        )
    )


def as_evaluated(configuration: dict) -> list[str]:
    """Each part of a run's configuration that differs from the evaluated one."""
    if not EVALUATED.exists():
        return ["no evaluated configuration on file"]
    evaluated = json.loads(EVALUATED.read_text())["configuration"]
    return [
        part.removeprefix("cobalt.")
        for part, value in configuration.items()
        if evaluated.get(part) != value
    ]


def show_output(output: Finding | Flagged | None) -> None:
    if isinstance(output, Flagged):
        print(f"flagged: {output.reason}")
        for problem in output.problems:
            say(f"- {problem}", "  ")
        output = output.finding
    if output is None:
        return
    print(f"finding: {output.status}")
    if output.fault:
        print(f"  fault: {output.fault.document}, {output.fault.problem}")
    for label, value in (
        ("cause", output.cause),
        ("action", output.recommended_action),
        ("open question", output.open_question),
    ):
        if value:
            say(f"{label}: {value}", "  ")
    print(f"  evidence: {', '.join(e.record_id for e in output.evidence)}")


async def investigate(request: InvestigationRequest) -> dict:
    from .agents import telemetry
    from .agents.interpreter import interpreter
    from .agents.steps import investigation

    case = casework.begin(request)
    print(
        f"{case['case_id']} {request.shipment_id} investigating (asked by {request.requested_by})"
    )
    telemetry.setup(storage.folder() / "telemetry")
    agent = interpreter(middleware=[telemetry.keep_evidence])
    try:
        run = await telemetry.investigate(investigation(agent), agent, request)
    finally:
        telemetry.close()
    differs = as_evaluated(run["configuration"])
    print(f"trace {run['trace_id']}")
    print(
        f"configuration: {'as evaluated' if not differs else 'NOT as evaluated: ' + ', '.join(differs)}"
    )
    show_output(run["result"])
    case = casework.conclude(
        case["case_id"], run["result"], run["trace_id"], run["error"]
    )
    for request_ in approvals.everything():
        if (
            request_.case_id == case["case_id"]
            and request_.finding_id == run["trace_id"]
        ):
            say(
                f"{request_.request_id} refile {request_.document_id} against {request_.customs_case}: {request_.status}"
                + (f" ({request_.reason})" if request_.reason else "")
            )
    print(f"{case['case_id']} is now {case['state']}")
    tokens = run["usage"]
    print(
        f"tokens in {tokens.get('input_token_count', 0):,} ({tokens.get('cache_read_input_token_count', 0):,} cached),"
        f" out {tokens.get('output_token_count', 0):,}; cost ${run['cost_usd']:.5f}"
    )
    return case


def review() -> None:
    for request in gate.pending():
        doc = records.document(request.document_id)
        changed = (
            "no"
            if doc["version"] == request.expected_version
            else f"yes: version {request.expected_version} then, {doc['version']} now"
        )
        print(
            f"{request.request_id} {request.shipment_id}: refile {request.document_id} against {request.customs_case}"
        )
        say(f"asked by {request.requested_by}, expires {request.expires}", "  ")
        say(f"from the finding of investigation {request.finding_id}", "  ")
        say(
            f"now filed against {doc['filed_against_customs_case']}; changed since the request: {changed}",
            "  ",
        )
        say(
            f"store's rules: {records.check_refile(request.document_id, request.customs_case) or 'allow it'}",
            "  ",
        )
    if not gate.pending():
        print("no pending requests")


def outcome(answer: dict | None) -> str:
    """The document store's answer to a filing, in words."""
    if not answer:
        return ""
    if "error" in answer:
        return f" ({answer['error']}: {answer['message']})"
    return f" as {answer['filing']}; {answer['document_id']} now filed against {answer['now_filed_against']}"


def release_checks() -> None:
    """Close every filed case customs has cleared, and hand to a person any that waited too long.
    In production, a scheduled job runs this, as it runs the expiry sweep."""
    for case in cases.everything().values():
        if case["state"] == "filed":
            casework.check_release(case["case_id"])


def status(shipment_id: str | None) -> None:
    for case in cases.everything().values():
        if shipment_id and case["shipment_id"] != shipment_id:
            continue
        print(f"{case['case_id']} {case['shipment_id']}: {case['state']}")
        for event in case["events"]:
            arrow = f"{event.get('from', '')} -> {event['to']}".strip()
            say(
                f"{event['time'][11:19]} {arrow:<33} by {event['by']}: {event['detail']}",
                "  ",
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cobalt",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("reset")
    p = sub.add_parser("investigate")
    p.add_argument("shipment_id")
    p.add_argument("--as", dest="user", required=True)
    p.add_argument("--objective")
    sub.add_parser("review")
    p = sub.add_parser("decide")
    p.add_argument("request_id")
    p.add_argument("--as", dest="user", required=True)
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", action="store_true")
    choice.add_argument("--reject", action="store_true")
    p = sub.add_parser("recover")
    p.add_argument("request_id")
    sub.add_parser("customs")
    sub.add_parser("expire")
    p = sub.add_parser("status")
    p.add_argument("shipment_id", nargs="?")
    args = parser.parse_args()

    if args.command == "reset":
        records.reset()
        storage.save("cases", {})
        storage.save("approvals", {})
        print(f"stand-in records reset in {storage.folder()}/")
    elif args.command == "investigate":
        fields = {"shipment_id": args.shipment_id, "requested_by": args.user}
        if args.objective:
            fields["objective"] = args.objective
        try:
            asyncio.run(investigate(InvestigationRequest(**fields)))
        except casework.CaseBusy as busy:
            print(f"not investigated: {busy}")
    elif args.command == "review":
        gate.expire_due()
        release_checks()
        review()
    elif args.command == "decide":
        gate.expire_due()
        try:
            request = gate.decide(args.request_id, args.user, approve=args.approve)
        except PermissionError as refused:
            print(f"refused: {refused}")
            return
        say(f"{request.request_id}: {request.status}" + outcome(request.outcome))
        print(f"{request.case_id} is now {cases.get(request.case_id)['state']}")
    elif args.command == "recover":
        request = gate.recover(args.request_id)
        say(f"{request.request_id}: {request.status}" + outcome(request.outcome))
        print(f"{request.case_id} is now {cases.get(request.case_id)['state']}")
    elif args.command == "customs":
        print(
            f"customs cleared: {', '.join(records.customs_processes()) or 'nothing'}"
        )
        for case in cases.everything().values():
            if case["state"] == "filed":
                case = casework.check_release(case["case_id"])
                print(f"{case['case_id']} {case['shipment_id']} is {case['state']}")
    elif args.command == "expire":
        print(f"expired: {', '.join(gate.expire_due()) or 'nothing'}")
    elif args.command == "status":
        gate.expire_due()
        release_checks()
        status(args.shipment_id)
