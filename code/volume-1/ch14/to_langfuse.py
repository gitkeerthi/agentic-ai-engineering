"""Sending the investigation's spans to Langfuse as well as to the trace store.

Langfuse takes OpenTelemetry spans over OTLP/HTTP and maps most of what the framework records: the model, the
token counts, the agent and tool spans, and the release (the resource's `service.version`, as each observation's
version). Two things it reads that our spans don't carry:

- each model call's cost, as `gen_ai.usage.cost` on its chat span. The exporter adds it to a copy of the span on
  the way out, priced with agentlab's table at the time the call ended (Langfuse's own price table has no rate
  that follows the clock, and the lab model is half price off-peak);
- the run's case as its session, `session.id`, on every span: Langfuse filters only on what each observation
  carries. The run's shipment travels as OpenTelemetry baggage (telemetry.investigate sets it), and the contrib
  BaggageSpanProcessor copies it onto each span as the span starts.

A module, not a program: telemetry.setup(..., langfuse=True) uses it.
"""

import base64
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values
from langfuse import Langfuse
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.processor.baggage import BaggageSpanProcessor
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter

from agentlab.llm import PRICES, cost

ENV = Path(__file__).parent / "langfuse" / ".env"  # written by langfuse/new_env.py


def settings() -> dict:
    """Langfuse's address and the project's keys."""
    if not ENV.exists():
        raise SystemExit(f"No {ENV}: run ch14/langfuse/new_env.py, then docker compose up")
    return dotenv_values(ENV)


def client() -> Langfuse:
    """Langfuse's own client, for its API: scores and reads. Not for tracing: the
    framework's spans reach Langfuse through exporter()."""
    env = settings()
    return Langfuse(
        public_key=env["LANGFUSE_PUBLIC_KEY"],
        secret_key=env["LANGFUSE_SECRET_KEY"],
        base_url=env["LANGFUSE_BASE_URL"],
        tracing_enabled=False,
    )


def exporter() -> SpanExporter:
    env = settings()
    keys = f"{env['LANGFUSE_PUBLIC_KEY']}:{env['LANGFUSE_SECRET_KEY']}"
    return ForLangfuse(
        OTLPSpanExporter(
            endpoint=f"{env['LANGFUSE_BASE_URL']}/api/public/otel/v1/traces",
            headers={
                "Authorization": f"Basic {base64.b64encode(keys.encode()).decode()}",
                "x-langfuse-ingestion-version": "4",  # without it, spans can take minutes to appear
            },
        )
    )


def sessions() -> BaggageSpanProcessor:
    """Copies the shipment, carried as baggage, onto each span as session.id."""
    return BaggageSpanProcessor(lambda key: key == "session.id")


class ForLangfuse(SpanExporter):
    """An OTLP exporter that first adds each model call's cost, under the name Langfuse reads."""

    def __init__(self, otlp: SpanExporter) -> None:
        self.otlp = otlp

    def export(self, spans):
        return self.otlp.export([mapped(span) for span in spans])

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.otlp.force_flush(timeout_millis)

    def shutdown(self) -> None:
        self.otlp.shutdown()


def mapped(span: ReadableSpan) -> ReadableSpan:
    if span.attributes.get("gen_ai.operation.name") != "chat":
        return span
    price = call_cost(span.attributes, span.end_time)  # ①
    if price is None:
        return span
    return ReadableSpan(  # ② a copy: an ended span can't be changed
        name=span.name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes={**span.attributes, "gen_ai.usage.cost": price},
        events=span.events,
        links=span.links,
        kind=span.kind,
        status=span.status,
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


def call_cost(attributes: dict, end_time: int) -> float | None:
    """One model call's cost from its span's token counts; None for a model with no price."""
    model = attributes.get("gen_ai.response.model")
    if model not in PRICES:  # a provider may answer with a dated name: price what was asked for
        model = attributes.get("gen_ai.request.model")
    if model not in PRICES:
        return None
    return cost(
        {
            "time": datetime.fromtimestamp(end_time / 1e9, UTC).isoformat(),
            "model": model,
            "input": attributes.get("gen_ai.usage.input_tokens", 0),
            "cached": attributes.get("gen_ai.usage.cache_read.input_tokens", 0),
            "output": attributes.get("gen_ai.usage.output_tokens", 0),
        }
    )
