"""Chapter 15: each failure the application is designed for, run once, with scripted model replies and
lab faults in the stand-in systems. No model call. Prints, for each, what happened and where the case ended.

    uv run python ch15/failures.py
"""

import asyncio
import os
import sys
import tempfile
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["COBALT_STATE"] = (
    tempfile.mkdtemp()
)  # a scratch copy of the stand-in systems
sys.path.insert(
    0, str(Path(__file__).parents[1] / "tests")
)  # the tests' scripted client and findings

from cobalt_exceptions.agents.interpreter import interpreter  # noqa: E402
from cobalt_exceptions.agents.steps import investigation  # noqa: E402
from cobalt_exceptions.domain.contracts import Finding, Flagged, InvestigationRequest  # noqa: E402
from cobalt_exceptions.services import casework, gate  # noqa: E402
from cobalt_exceptions.systems import approvals, cases, records, storage  # noqa: E402
from findings import misfiled_invoice, rejected_invoice  # noqa: E402
from scripted import ScriptedClient  # noqa: E402


def fresh() -> None:
    records.reset()
    storage.save("cases", {})
    storage.save("approvals", {})


def investigate(
    shipment_id: str,
    replies: list,
    usage: dict | None = None,
    by: str = "analyst-017",
) -> tuple[dict, int]:
    """Open a case, run the workflow with scripted replies, record the ending. Returns the case and model calls."""
    request = InvestigationRequest(shipment_id=shipment_id, requested_by=by)
    case = casework.begin(request)
    client = ScriptedClient(replies, usage=usage)
    [output] = asyncio.run(
        investigation(interpreter(client)).run(request)
    ).get_outputs()
    return casework.conclude(
        case["case_id"], output, trace_id=f"trace-{case['case_id']}"
    ), len(client.sent)


def ending(case: dict) -> str:
    if case["flag"]:
        return f"flagged {case['flag']['reason']}: {'; '.join(case['flag']['problems'])}"
    return (
        f"finding {case['finding']['status']}" if case["finding"] else "no finding"
    )


def line(text: str) -> None:
    print(textwrap.fill(text, 85, initial_indent="  ", subsequent_indent="    "))


def show(title: str, case: dict, calls: int | None = None, note: str = "") -> None:
    print(f"\n{title}")
    if calls is not None:
        line(f"{ending(case)} ({calls} model call{'s' if calls != 1 else ''})")
    if note:
        line(note)
    line(f"case {case['case_id']}: {case['state']}")


REPORT = ("report_finding", misfiled_invoice(), "c9")

fresh()
records.make_busy("documents", 2)
case, calls = investigate("SH-4471", [REPORT])
show("1. Document store busy twice, then answers", case, calls)

fresh()
records.make_busy("documents", 3)
case, calls = investigate("SH-4471", [])
show("2. Document store busy on every try", case, calls)

fresh()
records.make_busy("messages", 3)
unsure = rejected_invoice(
    status="undetermined",
    cause=None,
    fault=None,
    open_question="Why does customs show the invoice as not received?",
)
unsure["evidence"] = [
    {"record_id": "RTM-88520", "fact": "the invoice is not received"}
]
case, calls = investigate(
    "SH-4731",
    [
        ("search_messages", {"query": "invoice"}, "c1"),
        ("report_finding", unsure, "c2"),
    ],
)
show(
    "3. Message archive busy on every try",
    case,
    calls,
    "the tool returned: The message archive is unavailable. Don't retry; ...",
)

fresh()
case, calls = investigate(
    "SH-4471", [("report_finding", misfiled_invoice(fault=None), "c1"), REPORT]
)
show(
    "4. A report the contract refuses (cause_found with no fault), then a valid one",
    case,
    calls,
)

fresh()
disguised = misfiled_invoice(
    shipment_id="SH-4588",
    cause="The records do not identify which document is outstanding.",
    fault={"document": "commercial invoice", "problem": "not_uploaded"},
    refiling=None,
    evidence=[
        {"record_id": "RTM-88377", "fact": "on hold for a document not received"}
    ],
)
case, calls = investigate("SH-4588", [("report_finding", disguised, "c1")])
show(
    "5. A cause the records don't show (Chapter 13's disguised abstention)",
    case,
    calls,
)

fresh()
case, calls = investigate("SH-4731", [("report_finding", rejected_invoice(), "c1")])
show("6. A customs message cited without being retrieved", case, calls)

fresh()
heavy = {"input_token_count": 20_000, "output_token_count": 11_000}
case, calls = investigate(
    "SH-4731", [("search_messages", {"query": "invoice"}, "c1"), REPORT], usage=heavy
)
show("7. Token budget spent", case, calls)

fresh()
searches = [("search_messages", {"query": f"word {i}"}, f"c{i}") for i in range(6)]
case, calls = investigate("SH-4731", [*searches, "I could not decide."])
show("8. The agent keeps searching until the loop limit", case, calls)

fresh()
case, _ = investigate("SH-4471", [REPORT])
now = datetime.now(UTC)
other = approvals.get("REQ-0001").model_copy(
    update={
        "request_id": "REQ-0002",
        "document_id": "DOC-5530",
        "requested_by": "analyst-022",
    }
)
refused = gate.submit(other)
show(
    "9. A refiling request that doesn't match the finding",
    cases.get(case["case_id"]),
    note=f"REQ-0002 {refused.status}: {refused.reason}",
)

duplicate = approvals.get("REQ-0001").model_copy(
    update={"request_id": "REQ-0003", "requested_by": "analyst-022"}
)
refused = gate.submit(duplicate)
show(
    "10. A second request while the first one waits",
    cases.get(case["case_id"]),
    note=f"REQ-0003 {refused.status}: {refused.reason}",
)

fresh()
case, _ = investigate("SH-4471", [REPORT], by="lead-044")
try:
    gate.decide("REQ-0001", "lead-044", approve=True)
except PermissionError as error:
    show(
        "11. The approver who asked for the investigation approves its refiling",
        cases.get(case["case_id"]),
        note=f"refused: {error}",
    )

fresh()
case, _ = investigate("SH-4471", [REPORT])
gate.expire_due(now + timedelta(hours=25))
show(
    "12. Nobody answers within 24 hours",
    cases.get(case["case_id"]),
    note=f"REQ-0001 {approvals.get('REQ-0001').status}",
)

fresh()
case, _ = investigate("SH-4471", [REPORT])
records.colleague_replaces("DOC-5531")
request = gate.decide("REQ-0001", "lead-031", approve=True)
show(
    "13. The document changed after the request was made, then the approval",
    cases.get(case["case_id"]),
    note=f"REQ-0001 {request.status}: {request.outcome['message']}",
)

fresh()
case, _ = investigate("SH-4471", [REPORT])
records.drop_replies(1)
request = gate.decide("REQ-0001", "lead-031", approve=True)
filings = len(records.load_records()["filings"])
show(
    "14. The store's reply is lost once",
    cases.get(case["case_id"]),
    note=f"REQ-0001 {request.status} {request.outcome['filing']}; filings in the store: {filings}",
)

fresh()
case, _ = investigate("SH-4471", [REPORT])
records.drop_replies(3)
request = gate.decide("REQ-0001", "lead-031", approve=True)
before = cases.get(case["case_id"])["state"]
request = gate.recover("REQ-0001")
filings = len(records.load_records()["filings"])
show(
    "15. Every reply lost, then recovered",
    cases.get(case["case_id"]),
    note=f"after the decision: {before}; after recover: REQ-0001 {request.status}; filings in the store: {filings}",
)

case = casework.check_release(case["case_id"])
show(
    "16. Filed, but customs hasn't processed it",
    case,
    note="customs case RTM-88213: " + records.customs_case("RTM-88213")["status"],
)
records.customs_processes()
case = casework.check_release(case["case_id"])
show(
    "    ... then customs clears it",
    case,
    note="customs case RTM-88213: " + records.customs_case("RTM-88213")["status"],
)

fresh()
case, _ = investigate("SH-4471", [REPORT])
gate.decide("REQ-0001", "lead-031", approve=True)
later = datetime.now(UTC) + timedelta(days=4)
show(
    "17. Filed, and customs still hasn't cleared it four days later",
    casework.check_release(case["case_id"], later),
    note="customs case RTM-88213: " + records.customs_case("RTM-88213")["status"],
)

fresh()
case, _ = investigate("SH-4471", [REPORT])


def times_out(*args, **kwargs):
    raise TimeoutError("no answer from the store")


real_refile, gate.filing.refile = gate.filing.refile, times_out  # a lab fault
request = gate.decide("REQ-0001", "lead-031", approve=True)
gate.filing.refile = real_refile
show(
    "18. The filing call times out every time",
    cases.get(case["case_id"]),
    note=f"REQ-0001 {request.status}; filings in the store: "
    f"{len(records.load_records()['filings'])}",
)

fresh()
case, _ = investigate("SH-4471", [REPORT])
gate.decide("REQ-0001", "lead-031", approve=False)
again = approvals.get("REQ-0001").model_copy(
    update={"request_id": "REQ-0002", "status": "pending"}
)
refused = gate.submit(again)
show(
    "19. A matching request after the first was rejected",
    cases.get(case["case_id"]),
    note=f"REQ-0002 {refused.status}: {refused.reason}",
)

fresh()
investigate("SH-4471", [REPORT])
try:
    casework.begin(
        InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-022")
    )
except casework.CaseBusy as busy:
    print("\n20. Investigating again while a refiling is in flight")
    line(f"refused: {busy}")

fresh()
case, _ = investigate("SH-4471", [REPORT])
gate.decide("REQ-0001", "lead-031", approve=False)
case, _ = investigate("SH-4471", [REPORT], by="lead-044")
try:
    gate.decide("REQ-0002", "lead-044", approve=True)
except PermissionError as error:
    show(
        "21. The approver who asked for the second investigation approves its refiling",
        cases.get(case["case_id"]),
        note=f"refused: {error}",
    )

fresh()
case, _ = investigate("SH-4471", [REPORT])
gate.decide("REQ-0001", "lead-031", approve=False)
casework.begin(InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-022"))
during = approvals.get("REQ-0001").model_copy(
    update={"request_id": "REQ-0002", "status": "pending"}
)
refused = gate.submit(during)
show(
    "22. A request built from the old finding while a second investigation runs",
    cases.get(case["case_id"]),
    note=f"REQ-0002 {refused.status}: {refused.reason}",
)
