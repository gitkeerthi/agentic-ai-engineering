"""What every investigation leaves behind, so that it can be explained later (Chapter 14's design).

- OpenTelemetry, set up once with the framework's `configure_otel_providers`, exporting spans,
  logs and metrics to JSON Lines files in a store folder, a stand-in for a trace backend.
  Sensitive data stays off.
- The seven-part configuration a run used, as attributes on the run's root span and in its run record.
- The evidence: what the agent was sent and what it replied, kept by agent middleware in a
  separate store keyed by the trace ID, because the trace holds no content.
- A run record per investigation, with the same trace ID, usage and cost: what the evaluation scores.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from importlib.metadata import version

from agent_framework import __version__ as framework_version
from agent_framework import agent_middleware
from agent_framework.observability import (
    configure_otel_providers,
    get_meter,
    get_tracer,
)
from opentelemetry import trace
from opentelemetry._logs import get_logger_provider
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.metrics import get_meter_provider
from opentelemetry.sdk._logs.export import ConsoleLogRecordExporter
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

from agentlab.llm import PRICES, cost

from .interpreter import TIME_LIMIT

from ..domain.contracts import Finding, Flagged, InvestigationRequest

PACKAGE = Path(__file__).parents[1]
RELEASE = "2026.11.15"  # the application's release; a build would stamp it
PRICE_TABLE = "2026-10-31"  # the date of agentlab's prices, recorded with each cost
# The code a run's behavior depends on: the rules and contracts, the systems' clients
# (retries, search), the steps and the agent. Not the CLI, the gate or this file.
CODE = [
    *sorted((PACKAGE / "domain").glob("*.py")),
    *sorted((PACKAGE / "systems").glob("*.py")),
    PACKAGE / "agents" / "steps.py",
    PACKAGE / "agents" / "interpreter.py",
]
CLIENT = PACKAGE.parent / "agentlab" / "llm.py"  # settings applied at call time
SCOPE = "cobalt.investigation"

log = logging.getLogger("cobalt.investigation")
log.setLevel(logging.INFO)
stores: dict = {}


def setup(store: Path, sensitive: bool = False) -> Path:
    """Turn on telemetry for this process, writing to the store folder. Call once."""
    store.mkdir(parents=True, exist_ok=True)
    stores.update(
        {
            kind: (store / f"{kind}.jsonl").open("a")
            for kind in ("spans", "logs", "metrics", "evidence", "runs")
        }
    )
    configure_otel_providers(
        service_name="cobalt-exceptions",
        service_version=RELEASE,
        resource_attributes={"deployment.environment.name": "local"},
        enable_sensitive_data=sensitive,
        exporters=[
            ConsoleSpanExporter(
                out=stores["spans"],
                formatter=lambda s: s.to_json(indent=None) + "\n",
            ),
            ConsoleLogRecordExporter(
                out=stores["logs"], formatter=lambda r: r.to_json(indent=None) + "\n"
            ),
            ConsoleMetricExporter(
                out=stores["metrics"],
                formatter=lambda m: m.to_json(indent=None) + "\n",
            ),
        ],
    )
    log.addHandler(LoggingHandler(logger_provider=get_logger_provider()))
    return store


def close() -> None:
    """Flush every exporter and close the store files."""
    for provider in (
        trace.get_tracer_provider(),
        get_logger_provider(),
        get_meter_provider(),
    ):
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    for file in stores.values():
        file.close()
    stores.clear()


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def configuration(agent) -> dict:
    """The seven parts that decide how a run behaves, beyond the records."""
    options = agent.default_options
    schemas = [tool.to_json_schema_spec() for tool in options["tools"]]
    return {
        "cobalt.release": RELEASE,
        "cobalt.instructions.md5": md5(options["instructions"]),
        "cobalt.tools.md5": md5(
            json.dumps(schemas, sort_keys=True)
        ),  # the contract is the report tool's schema
        "cobalt.model": agent.client.model,
        "cobalt.request_settings.md5": md5(
            CLIENT.read_text()
            + json.dumps(
                agent.client.function_invocation_configuration,
                sort_keys=True,
                default=str,
            )
        ),
        # the framework and the provider adapter that shapes every request
        "cobalt.framework.version": f"{framework_version}+openai-{version('agent-framework-openai')}",
        "cobalt.code.md5": md5("".join(path.read_text() for path in CODE)),
    }


def correlation_id() -> str:
    """The trace ID, or, if tracing isn't set up, an ID of our own (Chapter 14)."""
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        return format(context.trace_id, "032x")
    log.warning("no trace context: records get their own ID, and no trace exists")
    return uuid.uuid4().hex


def write(kind: str, record: dict) -> None:
    if kind in stores:
        stores[kind].write(json.dumps(record) + "\n")
        stores[kind].flush()


def read(fetch, *ids: str):
    """One read of Cobalt's records as a span: which read, which records, whether it failed."""
    tracer = get_tracer(SCOPE, RELEASE)
    with tracer.start_as_current_span(
        f"read {fetch.__name__}",
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attribute("cobalt.record_ids", list(ids))  # IDs, never contents
        try:
            result = fetch(*ids)
        except Exception as error:
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error.type", type(error).__name__)
            raise
        if isinstance(result, dict) and "error" in result:
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error.type", "record_unavailable")
        return result


usage: ContextVar[dict | None] = ContextVar("usage", default=None)
run_id: ContextVar[str | None] = ContextVar("run_id", default=None)


@agent_middleware
async def keep_evidence(context, call_next) -> None:
    """Keep what the agent was sent and replied, under the run's trace ID, even when the run raises."""
    try:
        await call_next()
    finally:
        result = context.result
        totals = usage.get()
        for key, count in ((result.usage_details if result else None) or {}).items():
            if totals is not None and isinstance(count, int):
                totals[key] = totals.get(key, 0) + count
        write(
            "evidence",
            {
                "trace_id": run_id.get(None) or correlation_id(),
                "instructions_md5": md5(
                    context.agent.default_options["instructions"]
                ),
                "sent": [m.to_dict() for m in context.messages],
                # What the providers render from: agent middleware runs before they add their messages.
                "case_file": (context.session.state.get("case_file") or {}).get(
                    "case_file"
                )
                if context.session
                else None,
                "response": result.to_dict() if result else None,
            },
        )


def run_cost(model: str, tokens: dict) -> float:
    if model not in PRICES:
        return 0.0  # the tests' scripted client
    entry = {
        "time": datetime.now(UTC).isoformat(),
        "model": model,
        "input": tokens.get("input_token_count", 0),
        "cached": tokens.get("cache_read_input_token_count", 0),
        "output": tokens.get("output_token_count", 0),
    }
    return cost(entry)


investigations = None  # the business metric: one count per run, by how it ended


async def investigate(workflow, agent, request: InvestigationRequest) -> dict:
    """Run one investigation inside a root span with its configuration, usage, cost and outcome,
    under a hard time limit. Returns the run record, which carries the trace ID."""
    global investigations
    investigations = investigations or get_meter(SCOPE, RELEASE).create_counter(
        "cobalt.investigations", description="Investigations run, by outcome"
    )
    config = configuration(agent)
    tracer = get_tracer(SCOPE, RELEASE)
    attributes = {
        "cobalt.shipment_id": request.shipment_id,
        "enduser.id": request.requested_by,
        **config,
    }
    with tracer.start_as_current_span("investigate", attributes=attributes) as root:
        run_id.set(correlation_id())
        usage.set({})
        output, error = None, ""
        try:
            async with asyncio.timeout(TIME_LIMIT):
                [output] = (await workflow.run(request)).get_outputs()
        except Exception as exc:  # the case goes to a person; the trace says why
            error = type(exc).__name__
            root.set_status(Status(StatusCode.ERROR))
            log.error("%s failed: %s", request.shipment_id, error)
        outcome = (
            "failed"
            if output is None
            else "flagged"
            if isinstance(output, Flagged)
            else "finding"
        )
        reason = output.reason if isinstance(output, Flagged) else ""
        tokens = usage.get()
        spent = run_cost(agent.client.model, tokens)
        root.set_attributes(
            {
                "cobalt.outcome": outcome,
                "cobalt.flag_reason": reason,
                "cobalt.usage.input_tokens": tokens.get("input_token_count", 0),
                "cobalt.usage.cached_input_tokens": tokens.get(
                    "cache_read_input_token_count", 0
                ),
                "cobalt.usage.output_tokens": tokens.get("output_token_count", 0),
                "cobalt.cost_usd": spent,
                "cobalt.price_table": PRICE_TABLE,
            }
        )
        if reason:
            log.warning("%s flagged for a person: %s", request.shipment_id, reason)
        investigations.add(1, {"outcome": outcome, "reason": reason})
        record = {
            "trace_id": run_id.get(),
            "time": datetime.now(UTC).isoformat(timespec="seconds"),
            "shipment_id": request.shipment_id,
            "requested_by": request.requested_by,
            "configuration": config,
            "outcome": outcome,
            "error": error,
            "output": output.model_dump() if output is not None else None,
            "usage": tokens,
            "cost_usd": spent,
        }
        write("runs", record)
    record["result"] = output  # the typed object, for the caller; not stored
    return record


def as_output(saved: dict | None) -> Finding | Flagged | None:
    """A stored output back as its type."""
    if saved is None:
        return None
    return (
        Flagged.model_validate(saved)
        if "reason" in saved
        else Finding.model_validate(saved)
    )
