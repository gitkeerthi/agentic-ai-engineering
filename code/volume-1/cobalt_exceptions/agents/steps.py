"""The investigation as a workflow (Chapter 11's shape): three reads in the procedure's order with
no model, one step where the agent interprets what they gathered, and a check of the agent's
finding before anyone sees it. The rules each step applies live in the domain; these executors
only read, call those rules, and pass messages on. Each step is a class, so every workflow gets its
own instances.
"""

from dataclasses import asdict, dataclass

from agent_framework import (
    Agent,
    AgentSession,
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)
from typing_extensions import Never

from ..domain.contracts import CaseFile, Finding, Flagged, InvestigationRequest
from ..domain.procedure import after_case, after_shipment, check_finding
from ..systems import records
from ..systems.records import Unavailable
from .interpreter import (
    CaseFileContext,
    TokenBudget,
    reported_finding,
    retrieved_messages,
)
from .telemetry import read


@dataclass
class CustomsShipment:
    request: InvestigationRequest
    shipment: dict


@dataclass
class OpenCase:
    request: InvestigationRequest
    shipment: dict
    case_id: str
    case: dict
    required: list[dict]


@dataclass
class Gathered:
    request: InvestigationRequest
    case_file: CaseFile


@dataclass
class Proposed:
    case_file: CaseFile
    finding: Finding | None
    retrieved: dict[str, dict]  # the messages the agent's searches returned
    note: str  # why there is no finding, when there isn't one


class LoadShipment(Executor):
    @handler
    async def load(
        self,
        request: InvestigationRequest,
        ctx: WorkflowContext[CustomsShipment, Finding | Flagged],
    ) -> None:
        shipment = read(records.shipment_status, request.shipment_id)
        if ending := after_shipment(request.shipment_id, shipment):
            await ctx.yield_output(ending)
        else:
            await ctx.send_message(CustomsShipment(request, shipment))


class LoadCase(Executor):
    @handler
    async def load(
        self,
        found: CustomsShipment,
        ctx: WorkflowContext[OpenCase, Finding | Flagged],
    ) -> None:
        case_id = found.shipment["customs_case"]
        case = read(records.customs_case, case_id)
        required = read(records.required_documents, case_id)
        if ending := after_case(
            found.request.shipment_id, found.shipment, case_id, case, required
        ):
            await ctx.yield_output(ending)
        else:
            await ctx.send_message(
                OpenCase(found.request, found.shipment, case_id, case, required)
            )


class CheckDocuments(Executor):
    @handler
    async def check(
        self, case: OpenCase, ctx: WorkflowContext[Gathered, Flagged]
    ) -> None:
        shipment_id = case.request.shipment_id
        filings = {}
        for item in case.required:  # every required document, received or not
            try:
                filings[item["document"]] = read(
                    records.document_search, shipment_id, item["document"]
                )
            except Unavailable as error:  # still busy after the client's retries
                problem = (
                    f"{error}: what's on file is unknown, so nothing was concluded"
                )
                await ctx.yield_output(
                    Flagged(
                        shipment_id=shipment_id,
                        reason="records_unavailable",
                        finding=None,
                        problems=[problem],
                    )
                )
                return
        elsewhere = {
            f["filed_against_customs_case"]
            for f in filings.values()
            if f.get("filed_against_customs_case") not in (None, case.case_id)
        }
        other_cases = {
            other: read(records.customs_case, other) for other in sorted(elsewhere)
        }
        if missing := [
            other for other, record in other_cases.items() if "error" in record
        ]:
            problem = (
                f"documents are filed against cases that aren't on file: {missing}"
            )
            await ctx.yield_output(
                Flagged(
                    shipment_id=shipment_id,
                    reason="records_missing",
                    finding=None,
                    problems=[problem],
                )
            )
            return
        case_file = CaseFile(
            shipment_id,
            case.shipment,
            case.case_id,
            case.case,
            case.required,
            filings,
            other_cases,
        )
        await ctx.send_message(Gathered(case.request, case_file))


class Interpret(Executor):
    """The one step that needs judgment: the agent reads the case file and may search the messages."""

    def __init__(self, agent: Agent):
        super().__init__(id="interpret")
        self.agent = agent

    @handler
    async def interpret(
        self, gathered: Gathered, ctx: WorkflowContext[Proposed]
    ) -> None:
        case_file = gathered.case_file
        session = AgentSession()
        session.state[CaseFileContext.SOURCE] = {
            "case_file": asdict(case_file)
        }  # ①
        budget = TokenBudget()
        result = await self.agent.run(
            gathered.request.objective,
            session=session,
            middleware=[budget],
            function_invocation_kwargs={
                "shipment_id": case_file.shipment_id  # ②
            },
        )
        finding = reported_finding(result)
        if finding:
            note = ""
        elif result.additional_properties.get("budget_spent"):
            note = (
                f"the agent spent its token budget ({budget.budget}) "
                "without a valid report"
            )
        else:
            note = "the agent reported no valid finding"
        await ctx.send_message(
            Proposed(case_file, finding, retrieved_messages(result), note)
        )


class CheckFinding(Executor):
    @handler
    async def check(
        self, proposed: Proposed, ctx: WorkflowContext[Never, Finding | Flagged]
    ) -> None:
        await ctx.yield_output(
            check_finding(
                proposed.finding,
                proposed.case_file,
                proposed.retrieved,
                proposed.note,
            )
        )


def investigation(agent: Agent):
    """New executors and a new workflow for one request. The agent can be shared."""
    steps = [
        LoadShipment(id="load_shipment"),
        LoadCase(id="load_case"),
        CheckDocuments(id="check_documents"),
        Interpret(agent),
        CheckFinding(id="check_finding"),
    ]
    return (
        WorkflowBuilder(start_executor=steps[0], name="investigation")
        .add_chain(steps)
        .build()
    )
