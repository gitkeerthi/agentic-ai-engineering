"""Chapter 11's workflow steps, unchanged: Cobalt's procedure for a customs hold as executors, and the messages
between them.

Three steps read the records in the procedure's order, with no model. One step asks an agent to interpret what
they gathered, and the last checks the agent's finding against the same records before anyone sees it. Each
step is a class, so every workflow gets its own instances: an executor handles one message at a time.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Literal

from agent_framework import (
    Agent,
    Executor,
    FunctionTool,
    MiddlewareTermination,
    WorkflowBuilder,
    WorkflowContext,
    function_middleware,
    handler,
)
from typing_extensions import Never

from agentlab.llm import make_client
from cobalt import (
    customs_case,
    document_search,
    required_documents,
    shipment_status,
)
from contracts import Evidence, Finding, record_problems


@dataclass
class CustomsShipment:
    """A shipment with a customs case: what the procedure starts from."""

    shipment_id: str
    shipment: dict


@dataclass
class OpenCase:
    shipment_id: str
    shipment: dict
    case_id: str
    case: dict
    required: list[dict]


@dataclass
class CaseFile:
    """All the procedure gathers for one held shipment: the records the
    agent reads."""

    shipment_id: str
    shipment: dict
    case_id: str
    case: dict
    required: list[dict]
    filings: dict[str, dict]  # document type -> where the store has it filed
    # cases documents are filed against
    other_cases: dict[str, dict] = field(default_factory=dict)


@dataclass
class Proposed:
    case_file: CaseFile
    finding: Finding | None
    note: str  # why there is no finding, when there isn't one


Reason = Literal[
    "unknown_shipment",  # the requester should check the ID
    "outside_procedure",  # a hold this procedure doesn't cover
    "records_missing",  # a record the procedure needs isn't on file
    "no_usable_finding",  # couldn't tell, said nothing's wrong, or didn't report
    "finding_problems",  # the finding says something the records don't support
]


@dataclass
class Flagged:
    """A case someone must look at before anything happens, and why."""

    shipment_id: str
    reason: Reason  # what the caller routes on
    finding: Finding | None
    problems: list[str]  # for the person who reads it


class StoreUnavailable(Exception):
    """The document store couldn't answer, so what's on file is unknown."""


def no_hold(shipment_id: str, shipment: dict, case_id: str | None = None) -> Finding:
    """Cobalt's rule: not held, and no customs case on hold, means nothing holds it."""
    fact = f"{shipment['status']} in {shipment['location']}, due {shipment['due']}"
    evidence = [
        Evidence(
            record_id=shipment_id,
            fact=fact if case_id else f"{fact}, no customs case",
        )
    ]
    if case_id:
        evidence.append(
            Evidence(record_id=case_id, fact="the customs case isn't on hold")
        )
    return Finding(
        shipment_id=shipment_id,
        status="nothing_wrong",
        cause=None,
        evidence=evidence,
        recommended_action=None,
        refiling=None,
    )


def outside_procedure(shipment_id: str, shipment: dict) -> Flagged:
    problem = f"{shipment['status']} with no customs case: outside this procedure"
    return Flagged(shipment_id, "outside_procedure", None, [problem])


# The hold reasons this procedure covers. Cobalt's case records give the reason as a
# fixed value, so this is a rule, not a reading of free text.
DOCUMENT_HOLDS = {"required document not received"}


def covered(case: dict) -> bool:
    """Is the customs case on hold for a reason this procedure covers?"""
    return case["status"] == "on hold" and case["hold_reason"] in DOCUMENT_HOLDS


def another_hold(shipment_id: str, case_id: str, case: dict) -> Flagged:
    """Held, but not by a customs hold over documents: outside this procedure."""
    if case["status"] == "on hold":
        reason = case["hold_reason"] or "no recorded reason"
        why = f"customs case {case_id} is on hold for {reason}"
    else:
        why = f"held, but customs case {case_id} is {case['status']}"
    return Flagged(
        shipment_id, "outside_procedure", None, [f"{why}: outside this procedure"]
    )


class LoadShipment(Executor):
    @handler
    async def load(
        self,
        shipment_id: str,
        ctx: WorkflowContext[CustomsShipment, Finding | Flagged],
    ) -> None:
        shipment = shipment_status(shipment_id)
        if "error" in shipment:
            await ctx.yield_output(
                Flagged(shipment_id, "unknown_shipment", None, [shipment["error"]])
            )  # ①
        elif shipment["customs_case"] is None and shipment["status"] != "held":
            await ctx.yield_output(no_hold(shipment_id, shipment))  # ②
        elif shipment["customs_case"] is None:
            await ctx.yield_output(outside_procedure(shipment_id, shipment))  # ③
        else:
            await ctx.send_message(CustomsShipment(shipment_id, shipment))  # ④


class LoadCase(Executor):
    @handler
    async def load(
        self,
        found: CustomsShipment,
        ctx: WorkflowContext[OpenCase, Finding | Flagged],
    ) -> None:
        case_id = found.shipment["customs_case"]
        case = customs_case(case_id)
        required = required_documents(case_id)
        if "error" in case:
            problem = case["error"]
            await ctx.yield_output(
                Flagged(found.shipment_id, "records_missing", None, [problem])
            )  # ①
        elif found.shipment["status"] != "held" and case["status"] != "on hold":
            await ctx.yield_output(
                no_hold(found.shipment_id, found.shipment, case_id)
            )  # ②
        elif not covered(case):
            await ctx.yield_output(
                another_hold(found.shipment_id, case_id, case)
            )  # ③
        elif required is None:
            problem = f"customs case {case_id} has no list of required documents"
            await ctx.yield_output(
                Flagged(found.shipment_id, "records_missing", None, [problem])
            )  # ④
        else:
            await ctx.send_message(
                OpenCase(found.shipment_id, found.shipment, case_id, case, required)
            )


class CheckDocuments(Executor):
    @handler
    async def check(
        self, case: OpenCase, ctx: WorkflowContext[CaseFile, Flagged]
    ) -> None:
        filings = {}
        for item in case.required:  # every required document, received or not
            found = document_search(case.shipment_id, item["document"])
            if "error" in found:
                raise StoreUnavailable(found["error"])  # ①
            filings[item["document"]] = found
        elsewhere = {
            f["filed_against_customs_case"]
            for f in filings.values()
            if f.get("filed_against_customs_case") not in (None, case.case_id)
        }
        other_cases = {other: customs_case(other) for other in sorted(elsewhere)}
        missing = [
            other for other, record in other_cases.items() if "error" in record
        ]
        if missing:
            problem = (
                f"documents are filed against cases that aren't on file: {missing}"
            )
            await ctx.yield_output(
                Flagged(case.shipment_id, "records_missing", None, [problem])
            )  # ②
            return
        await ctx.send_message(
            CaseFile(
                case.shipment_id,
                case.shipment,
                case.case_id,
                case.case,
                case.required,
                filings,
                other_cases,
            )
        )


INSTRUCTIONS = """\
You interpret the records Cobalt Freight's procedure has gathered for one held
shipment.

The message holds every record the procedure collected, as JSON: the shipment, its
customs case, the documents the case requires, where each one is filed, and any other
customs case a document is filed against.
Work only from these records. Find what is holding the shipment and the action that
would fix it.
If the records can't tell you, say so with status undetermined.

Call report_finding once with your finding. Don't answer in text.

Limits:
- Recommend actions; never claim to have taken one."""


def report(**finding) -> str:
    """Report the finding to Cobalt's case system."""
    return "Recorded."


@function_middleware
async def stop_after_report(context, call_next) -> None:
    await call_next()
    if context.function.name == "report_finding":
        raise MiddlewareTermination("finding recorded", result=context.result)


def interpreter(client=None) -> Agent:
    report_finding = FunctionTool(
        name="report_finding",
        description=report.__doc__,
        func=report,
        input_model=Finding,
    )
    client = client or make_client()
    client.function_invocation_configuration["max_iterations"] = 3
    return Agent(
        client,
        INSTRUCTIONS,
        name="interpreter",
        tools=[report_finding],
        middleware=[stop_after_report],
    )


def reported_finding(result) -> Finding | None:
    """The finding from the last report_finding call the framework accepted, if any."""
    accepted = {
        c.call_id
        for m in result.messages
        for c in m.contents
        if c.type == "function_result" and c.result == "Recorded."
    }
    reports = [
        c
        for m in result.messages
        for c in m.contents
        if c.type == "function_call"
        and c.name == "report_finding"
        and c.call_id in accepted
    ]
    return Finding.model_validate_json(reports[-1].arguments) if reports else None


class Interpret(Executor):
    """The one step that needs judgment: an agent interprets the case file."""

    def __init__(self, agent: Agent):
        super().__init__(id="interpret")
        self.agent = agent

    @handler
    async def interpret(
        self, case_file: CaseFile, ctx: WorkflowContext[Proposed]
    ) -> None:
        result = await self.agent.run(json.dumps(asdict(case_file), indent=2))  # ①
        finding = reported_finding(result)  # ②
        note = "" if finding else "the agent reported no valid finding"
        await ctx.send_message(Proposed(case_file, finding, note))  # ③


def records_in(case_file: CaseFile) -> tuple[dict, dict, dict]:
    """The case file's records, shaped for record_problems(): what the agent saw."""
    shipments = {case_file.shipment_id: case_file.shipment}
    cases = {case_file.case_id: case_file.case, **case_file.other_cases}
    documents = {
        (case_file.shipment_id, kind): record
        for kind, record in case_file.filings.items()
        if "document_id" in record  # a search that found nothing has no document
    }
    return shipments, cases, documents


def ids_in(case_file: CaseFile) -> set[str]:
    """Every record ID the case file holds: the only IDs a finding may cite."""
    return set(re.findall(r"\b(?:SH|RTM|DOC)-\d+\b", json.dumps(asdict(case_file))))


class CheckFinding(Executor):
    @handler
    async def check(
        self, proposed: Proposed, ctx: WorkflowContext[Never, Finding | Flagged]
    ) -> None:
        finding, case_file = proposed.finding, proposed.case_file
        if finding is None:
            flagged = Flagged(
                case_file.shipment_id, "no_usable_finding", None, [proposed.note]
            )
            await ctx.yield_output(flagged)
            return
        problems = [
            f"{e.record_id} is cited but isn't in the case file"
            for e in finding.evidence
            if e.record_id not in ids_in(case_file)  # ①
        ]
        if finding.shipment_id != case_file.shipment_id:
            problems.append(
                f"the finding is about {finding.shipment_id}, "
                f"not {case_file.shipment_id}"
            )
        if finding.status == "undetermined":
            problems.append("the agent couldn't tell from the records")  # ②
        if finding.status == "nothing_wrong":
            problems.append(
                "nothing_wrong, but the shipment or its customs case is on hold"
            )  # ③
        problems += record_problems(finding, *records_in(case_file))  # ④
        if not problems:
            await ctx.yield_output(finding)
            return
        usable = finding.status == "cause_found"
        reason = "finding_problems" if usable else "no_usable_finding"
        await ctx.yield_output(
            Flagged(case_file.shipment_id, reason, finding, problems)
        )


def reads() -> list[Executor]:
    """New executors for the procedure's three reads."""
    return [
        LoadShipment(id="load_shipment"),
        LoadCase(id="load_case"),
        CheckDocuments(id="check_documents"),
    ]


def investigation(agent: Agent):
    """New executors and a new workflow for one request. The agent can be shared."""
    steps = [*reads(), Interpret(agent), CheckFinding(id="check_finding")]
    return (
        WorkflowBuilder(start_executor=steps[0], name="investigation")
        .add_chain(steps)
        .build()
    )
