"""Chapter 11 checks: what a workflow instance, and an executor instance, can be shared for. No model call.

1. The same investigation workflow, run twice: what the agent step is sent each time.
2. The same workflow instance, asked for a second run while the first is going.
3. Four workflows run at once, first sharing one executor object, then each with its own.
"""

import asyncio
import time

from agent_framework import (
    Executor,
    WorkflowBuilder,
    WorkflowContext,
    executor,
    handler,
)
from typing_extensions import Never

from scripted import ScriptedClient
from steps import interpreter, investigation

FINDING = {
    "shipment_id": "SH-4471",
    "status": "cause_found",
    "cause": "The commercial invoice is filed against customs case RTM-88124 instead of RTM-88213.",
    "evidence": [{"record_id": "DOC-5531", "fact": "Filed against RTM-88124."}],
    "recommended_action": "Refile DOC-5531 against RTM-88213.",
    "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"},
}


@executor(id="slow_read")
async def slow_read(shipment_id: str, ctx: WorkflowContext[Never, str]) -> None:
    await asyncio.sleep(0.5)  # a read that waits half a second on a system
    await ctx.yield_output(shipment_id)


class SlowRead(Executor):
    @handler
    async def read(self, shipment_id: str, ctx: WorkflowContext[Never, str]) -> None:
        await asyncio.sleep(0.5)
        await ctx.yield_output(shipment_id)


async def four_at_once(make_start) -> float:
    began = time.monotonic()
    workflows = [
        WorkflowBuilder(start_executor=make_start()).build() for _ in range(4)
    ]
    await asyncio.gather(*(w.run(f"SH-{4471 + i}") for i, w in enumerate(workflows)))
    return time.monotonic() - began


async def main() -> None:
    client = ScriptedClient(
        [
            ("report_finding", FINDING, "call_1"),
            ("report_finding", FINDING, "call_2"),
        ]
    )
    workflow = investigation(interpreter(client))
    for run in (1, 2):
        await workflow.run("SH-4471")
        sent, _ = client.sent[-1]
        print(
            f"1. Same workflow, run {run}: the agent was sent {len(sent)} message(s): {[m.role for m in sent]}"
        )

    workflow = investigation(
        interpreter(ScriptedClient([("report_finding", FINDING, "call_1")]))
    )
    first = workflow.run("SH-4471")  # started, not yet finished
    try:
        workflow.run("SH-4471")
    except Exception as error:
        print(
            f"2. A second run while the first is going: {type(error).__name__}: {error}"
        )
    await first

    shared = await four_at_once(lambda: slow_read)
    own = await four_at_once(lambda: SlowRead(id="slow_read"))
    print(
        f"3. Four workflows at once, one shared executor: {shared:.2f} s; an executor each: {own:.2f} s"
    )


asyncio.run(main())
