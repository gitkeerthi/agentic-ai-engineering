"""Chapter 11 check: which wiring mistakes the builder catches, and which ones get through to a run.

No model call. Two graphs fail to build. Two build and run, and their last message is dropped: one because no
edge leaves its sender, one because the sender sent a type it never declared. The program prints what each
run returned and, from the run's spans, what happened to the message. Last, a correct graph is given an input
of the wrong type.
"""

import asyncio

from agent_framework import WorkflowBuilder, WorkflowContext, executor
from agent_framework.observability import configure_otel_providers
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from typing_extensions import Never

from steps import CaseFile, CheckDocuments, CustomsShipment, LoadCase, LoadShipment

spans = InMemorySpanExporter()
configure_otel_providers(exporters=[spans])


load_shipment = LoadShipment(id="load_shipment")
load_case = LoadCase(id="load_case")
check_documents = CheckDocuments(id="check_documents")


@executor(id="hand_over")
async def hand_over(
    case_file: CaseFile, ctx: WorkflowContext[Never, CaseFile]
) -> None:
    await ctx.yield_output(case_file)


@executor(id="load_shipment_as_dict")
async def load_shipment_as_dict(
    shipment_id: str, ctx: WorkflowContext[CustomsShipment]
) -> None:
    await ctx.send_message(
        {"shipment_id": shipment_id}
    )  # declares CustomsShipment, sends a dict


def try_build(label: str, builder: WorkflowBuilder):
    try:
        return builder.build()
    except Exception as error:
        print(f"{label}\n  build refused: {type(error).__name__}: {error}\n")


async def try_run(label: str, workflow) -> None:
    spans.clear()
    result = await workflow.run("SH-4471")
    trace.get_tracer_provider().force_flush()
    finished = sorted(spans.get_finished_spans(), key=lambda span: span.start_time)
    sent = [
        span.attributes["message.type"]
        for span in finished
        if span.name == "message.send"
    ]
    delivered = [
        span.attributes["edge_group.delivery_status"]
        for span in finished
        if span.name.startswith("edge_group.process")
        and span.attributes.get("message.source_id", "")[:9] != "internal:"
    ]
    print(
        f"{label}\n  built; final state {result.get_final_state()}; outputs: {result.get_outputs()}"
    )
    print(f"  messages sent: {sent}; edge deliveries: {delivered}\n")


async def main() -> None:
    try_build(
        "1. An edge between steps whose types don't match (load_shipment -> check_documents)",
        WorkflowBuilder(start_executor=load_shipment).add_edge(
            load_shipment, check_documents
        ),
    )
    try_build(
        "2. Steps no path from the start reaches (check_documents -> hand_over)",
        WorkflowBuilder(start_executor=load_shipment)
        .add_edge(load_shipment, load_case)
        .add_edge(check_documents, hand_over),
    )
    await try_run(
        "3. The last edge left out: check_documents sends its case file, and no edge leaves it",
        WorkflowBuilder(start_executor=load_shipment)
        .add_chain([load_shipment, load_case, check_documents])
        .build(),
    )
    await try_run(
        "4. A step that sends a type it didn't declare",
        WorkflowBuilder(start_executor=load_shipment_as_dict)
        .add_edge(load_shipment_as_dict, load_case)
        .build(),
    )
    reads = WorkflowBuilder(start_executor=load_shipment).add_chain(
        [load_shipment, load_case, check_documents, hand_over]
    )
    try:
        await reads.build().run(4471)
    except Exception as error:
        print(
            f"5. An input of the wrong type: run(4471)\n  run refused: {type(error).__name__}: {error}"
        )


asyncio.run(main())
