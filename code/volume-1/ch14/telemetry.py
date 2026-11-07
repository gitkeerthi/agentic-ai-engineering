"""What every investigation run leaves behind, so that it can be explained later.

- OpenTelemetry, set up once with the framework's `configure_otel_providers`: the
  service's name and release on every span, log record and metric; spans, logs and
  metrics exported to files in `store/NAME/`, stand-ins for a trace backend.
  Sensitive data stays off, as in production.
- The configuration a run used, as attributes on the run's root span.
- The evidence: what the agent was sent and what it replied, kept by agent
  middleware in a separate store keyed by the trace ID, because the trace holds no
  content with sensitive data off.
- The case system's record of the outcome, carrying the same trace ID.

A module, not a program: observed.py, week.py and the tests use it.
"""

import hashlib
import json
import logging
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from agent_framework import __version__ as framework_version
from agent_framework import agent_middleware
from agent_framework.observability import (
    configure_otel_providers,
    get_meter,
    get_tracer,
)
from opentelemetry import baggage, context, trace
from opentelemetry._logs import get_logger_provider
from opentelemetry.metrics import get_meter_provider
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs.export import ConsoleLogRecordExporter
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

import to_langfuse
from agentlab.llm import PRICES, cost

HERE = Path(__file__).parent
RELEASE = "2026.11.2"  # the application's release; a build would stamp it
PRICE_TABLE = "2026-10-31"  # the date of agentlab's prices, recorded with each cost
CODE = ("steps.py", "contracts.py")  # the workflow code a run's behavior depends on
CLIENT = HERE.parent / "agentlab" / "llm.py"  # the client setup: per-call settings
SCOPE = "cobalt.investigation"  # our spans' and metrics' source, apart from the framework's

log = logging.getLogger("cobalt.investigation")
log.setLevel(logging.INFO)
stores: dict = {}


def setup(
    name: str,
    sensitive: bool = False,
    service: str = "cobalt-investigation",
    langfuse: bool = False,
) -> Path:
    """Turn on telemetry for this process, writing to store/NAME/, and sending spans
    to Langfuse as well if asked (to_langfuse.py). Call once."""
    store = HERE / "store" / name
    store.mkdir(parents=True, exist_ok=True)
    stores.update(
        {
            kind: (store / f"{kind}.jsonl").open("a")
            for kind in ("spans", "logs", "metrics", "cases", "evidence")
        }
    )
    configure_otel_providers(
        service_name=service,
        service_version=RELEASE,  # ①
        resource_attributes={"deployment.environment.name": "lab"},
        enable_sensitive_data=sensitive,
        exporters=[
            ConsoleSpanExporter(
                out=stores["spans"],
                formatter=lambda s: s.to_json(indent=None) + "\n",
            ),
            ConsoleLogRecordExporter(
                out=stores["logs"],
                formatter=lambda r: r.to_json(indent=None) + "\n",
            ),
            ConsoleMetricExporter(
                out=stores["metrics"],
                formatter=lambda m: m.to_json(indent=None) + "\n",
            ),
            *([to_langfuse.exporter()] if langfuse else []),
        ],
    )
    if langfuse:
        global send_session
        send_session = True
        trace.get_tracer_provider().add_span_processor(to_langfuse.sessions())
    log.addHandler(LoggingHandler(logger_provider=get_logger_provider()))  # ②
    return store


def flush() -> None:
    """Export every finished span and log record now, not at the next batch."""
    trace.get_tracer_provider().force_flush()
    get_logger_provider().force_flush()


def close() -> None:
    """Flush every exporter and close the store files."""
    for provider in (
        trace.get_tracer_provider(),
        get_logger_provider(),
        get_meter_provider(),
    ):
        provider.shutdown()
    for file in stores.values():
        file.close()


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def configuration(agent) -> dict:
    """What decides how a run behaves, beyond the records: one value per part."""
    options = agent.default_options
    schemas = [tool.to_json_schema_spec() for tool in options["tools"]]
    return {
        "cobalt.release": RELEASE,
        "cobalt.instructions.md5": md5(options["instructions"]),
        "cobalt.tools.md5": md5(json.dumps(schemas, sort_keys=True)),  # contract fields
        "cobalt.model": agent.client.model,
        "cobalt.framework.version": framework_version,
        "cobalt.code.md5": md5("".join((HERE / f).read_text() for f in CODE)),
        "cobalt.client.md5": md5(CLIENT.read_text()),  # request settings, e.g. reasoning
    }


def trace_id() -> str:
    """The current trace's ID, in the 32-character form trace tools display."""
    return format(trace.get_current_span().get_span_context().trace_id, "032x")


def correlation_id() -> str:
    """The ID every record of this run carries: the trace ID, or, if tracing isn't
    set up (no provider, so every trace ID is zero), an ID of our own."""
    if trace.get_current_span().get_span_context().is_valid:
        return trace_id()
    log.warning("no trace context: records get their own ID, and no trace exists")
    return uuid.uuid4().hex


def write(kind: str, record: dict) -> None:
    stores[kind].write(json.dumps(record) + "\n")
    stores[kind].flush()


def read(fetch, *ids: str) -> dict:
    """One read of Cobalt's records as a span: which read, which records, failure."""
    tracer = get_tracer(SCOPE, RELEASE)
    with tracer.start_as_current_span(
        f"read {fetch.__name__}", record_exception=False, set_status_on_exception=False
    ) as span:  # the SDK's defaults would record the exception's message
        span.set_attribute("cobalt.record_ids", list(ids))  # IDs, never contents
        try:
            result = fetch(*ids)
        except Exception as error:
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error.type", type(error).__name__)  # the class only
            raise
        if isinstance(result, dict) and "error" in result:
            span.set_status(Status(StatusCode.ERROR))  # ①
            span.set_attribute("error.type", "record_unavailable")
        return result


usage: ContextVar[dict | None] = ContextVar("usage", default=None)  # this run's tokens


@agent_middleware
async def keep_evidence(context, call_next) -> None:
    """Keep what the agent was sent and replied, under the run's trace ID, even
    when the agent's run raises: a failed run is the one most worth explaining."""
    try:
        await call_next()
    finally:
        result = context.result
        totals = usage.get()  # None outside investigate(): nothing to add to
        for key, count in ((result.usage_details if result else None) or {}).items():
            if totals is not None and isinstance(count, int):
                totals[key] = totals.get(key, 0) + count  # added: an agent may run twice
        write(
            "evidence",
            {
                "trace_id": run_id.get(None) or correlation_id(),
                "instructions_md5": md5(context.agent.default_options["instructions"]),
                "sent": context.messages[-1].text,
                "response": result.to_dict() if result else None,  # None: it raised
            },
        )


run_id: ContextVar[str | None] = ContextVar("run_id", default=None)
send_session = False  # setup(langfuse=True) sets it: the shipment goes in baggage
investigations = None  # the business metric: one count per run, by how it ended
CACHED = "cache_read_input_token_count"
REASON = "cobalt.flag_reason"


def run_cost(model: str, tokens: dict) -> float:
    """What the run's model calls cost, priced now, cached input at its own rate.
    A model with no price (the tests' scripted client) costs nothing."""
    if model not in PRICES:
        return 0.0
    entry = {
        "time": datetime.now(UTC).isoformat(),
        "model": model,
        "input": tokens.get("input_token_count", 0),
        "cached": tokens.get("cache_read_input_token_count", 0),
        "output": tokens.get("output_token_count", 0),
    }
    return cost(entry)


async def investigate(workflow, agent, shipment_id: str):
    """Run one investigation inside a root span that carries its configuration,
    usage, cost and outcome, and record the outcome in the case system with the
    trace ID. Returns the case record."""
    global investigations
    investigations = investigations or get_meter(SCOPE, RELEASE).create_counter(
        "cobalt.investigations", description="Investigations run, by outcome"
    )
    # baggage: in the run's context and any service it reaches, so IDs only
    session = baggage.set_baggage("session.id", shipment_id) if send_session else None
    token = context.attach(session) if session else None
    attributes = {"cobalt.shipment_id": shipment_id, **configuration(agent)}  # ①
    tracer = get_tracer(SCOPE, RELEASE)
    with tracer.start_as_current_span("investigate", attributes=attributes) as root:
        run_id.set(correlation_id())  # ②
        usage.set({})  # a fresh dict per run; a concurrent run sets its own
        output, outcome = None, {}
        try:
            [output] = (await workflow.run(shipment_id)).get_outputs()
            flagged = hasattr(output, "reason")
            finding = output.finding if flagged else output
            outcome = {
                "cobalt.outcome": "flagged" if flagged else "finding",
                REASON: output.reason if flagged else "",
                "cobalt.status": finding.status if finding else "",
            }
        except Exception as error:
            outcome = {
                "cobalt.outcome": "failed",
                REASON: "",
                "error.type": type(error).__name__,
            }
            root.set_status(Status(StatusCode.ERROR))
            log.error("%s failed: %s", shipment_id, outcome["error.type"])
        tokens = usage.get()
        root.set_attributes(
            {
                **outcome,
                "cobalt.usage.input_tokens": tokens.get("input_token_count", 0),
                "cobalt.usage.cached_input_tokens": tokens.get(CACHED, 0),
                "cobalt.usage.output_tokens": tokens.get("output_token_count", 0),
                "cobalt.cost_usd": run_cost(agent.client.model, tokens),  # ③
                "cobalt.price_table": PRICE_TABLE,
            }
        )
        if outcome["cobalt.outcome"] == "flagged":
            log.warning("%s flagged for review: %s", shipment_id, outcome[REASON])
        ending = {"outcome": outcome["cobalt.outcome"], "reason": outcome[REASON]}
        investigations.add(1, ending)
        record = {
            "trace_id": run_id.get(),  # ④
            "time": datetime.now(UTC).isoformat(timespec="seconds"),
            "shipment_id": shipment_id,
            "release": RELEASE,
            "outcome": outcome["cobalt.outcome"],
            "output": saved_form(output),
        }
        write("cases", record)
    if token:
        context.detach(token)
    return record


def saved_form(output) -> dict | None:
    """The workflow's output as the case system stores it: a Finding, or a Flagged
    result with its finding."""
    if output is None:
        return None
    if not hasattr(output, "reason"):
        return output.model_dump()
    finding = output.finding.model_dump() if output.finding else None
    return {
        "reason": output.reason,
        "finding": finding,
        "problems": output.problems,
    }
