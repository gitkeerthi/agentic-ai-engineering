"""Chapter 11 demo: the procedure's three reads as a workflow, with no model.

Three executors connected by edges read the records in the procedure's order; a fourth hands the case file to
the caller as the workflow's output. The program prints every event the run produced, then the output.
"""

import asyncio
import sys

from agent_framework import WorkflowBuilder, WorkflowContext, executor
from typing_extensions import Never

from steps import CaseFile, CheckDocuments, LoadCase, LoadShipment


@executor(id="hand_over")
async def hand_over(
    case_file: CaseFile, ctx: WorkflowContext[Never, CaseFile]
) -> None:
    await ctx.yield_output(case_file)


load_shipment = LoadShipment(id="load_shipment")  # ①
load_case = LoadCase(id="load_case")
check_documents = CheckDocuments(id="check_documents")

workflow = (
    WorkflowBuilder(start_executor=load_shipment)  # ②
    .add_edge(load_shipment, load_case)  # ③
    .add_edge(load_case, check_documents)
    .add_edge(check_documents, hand_over)
    .build()  # ④
)


async def main(shipment_id: str) -> None:
    result = await workflow.run(shipment_id)
    for event in result:
        detail = (
            type(event.data).__name__
            if event.type in ("executor_invoked", "output")
            else ""
        )
        print(f"{event.type:<20} {event.executor_id or '':<16} {detail}")
    print(f"\nFinal state: {result.get_final_state()}")
    for output in result.get_outputs():
        print(f"\nOutput ({type(output).__name__}):\n{output}")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "SH-4471"))
