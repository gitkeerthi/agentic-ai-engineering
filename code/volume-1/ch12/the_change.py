"""The change that opens Chapter 12: a busy document store no longer stops the investigation.

The edit looks like graceful degradation. `CheckDocuments` keeps each failed search in the case file and sends
it on, so the agent works with what it has instead of the run raising `StoreUnavailable`. Everything else is
Chapter 11's workflow. `workflow.py --with-change` runs it, and `pytest ch12 --with-change` tests it.
"""

from agent_framework import Agent, WorkflowBuilder, WorkflowContext, handler

from steps import (
    CaseFile,
    CheckDocuments,
    CheckFinding,
    Flagged,
    Interpret,
    LoadCase,
    LoadShipment,
    OpenCase,
)
from cobalt import customs_case, document_search


class CarryOnCheckDocuments(CheckDocuments):
    @handler
    async def check(
        self, case: OpenCase, ctx: WorkflowContext[CaseFile, Flagged]
    ) -> None:
        filings = {}
        for item in case.required:  # every required document, received or not
            found = document_search(case.shipment_id, item["document"])
            # The change: Chapter 11 raised StoreUnavailable here. Now a failed
            # search goes into the case file, and the agent sees the error.
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
            )
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


def investigation_with_change(agent: Agent):
    steps = [
        LoadShipment(id="load_shipment"),
        LoadCase(id="load_case"),
        CarryOnCheckDocuments(id="check_documents"),
        Interpret(agent),
        CheckFinding(id="check_finding"),
    ]
    return (
        WorkflowBuilder(start_executor=steps[0], name="investigation")
        .add_chain(steps)
        .build()
    )
