"""Chapter 14: the review service's side of propagate.py, run as its own process. It takes each case off the
review queue, continues the trace its headers name, and records that the case reached a person's queue.

    uv run python ch14/reviewer.py QUEUE_FILE
"""

import json
import sys
from pathlib import Path

from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind

import telemetry
from agent_framework.observability import get_tracer

tracer = get_tracer(telemetry.SCOPE)

queue = Path(sys.argv[1])
telemetry.setup(queue.parent.name, service="cobalt-review")
for line in queue.read_text().splitlines():
    message = json.loads(line)
    context = extract(message["headers"])  # ②
    with tracer.start_as_current_span(
        "assign to analyst", context=context, kind=SpanKind.CONSUMER
    ) as span:
        span.set_attribute("cobalt.shipment_id", message["shipment_id"])
        print(f"Reviewer picked up {message['shipment_id']} in trace {telemetry.trace_id()}")
telemetry.close()
