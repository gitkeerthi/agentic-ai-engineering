"""Chapter 4 demo: what a tool's exception leaves in its trace span, with sensitive data off or on. No model call.

    uv run python ch04/exception_in_span.py
    uv run python ch04/exception_in_span.py --sensitive
"""

import asyncio
import sys

from agent_framework import tool
from agent_framework.observability import configure_otel_providers
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

spans = InMemorySpanExporter()
configure_otel_providers(exporters=[spans], enable_sensitive_data="--sensitive" in sys.argv)


@tool
def look_up_customer(customer_id: str) -> str:
    """Look up a customer."""
    raise RuntimeError("query failed on table customers_pii")


async def call_tool() -> None:
    try:
        await look_up_customer.invoke(arguments={"customer_id": "C-1"})
    except RuntimeError as error:
        print(f"The tool raised: {error}")


asyncio.run(call_tool())
trace.get_tracer_provider().force_flush()
for span in spans.get_finished_spans():
    print(f"\nSpan {span.name}: status {span.status.status_code.name}, description {span.status.description!r}")
    print(f"  error.type: {span.attributes.get('error.type')}")
    for event in span.events:
        print(f"  event {event.name}: {event.attributes['exception.message']}")
