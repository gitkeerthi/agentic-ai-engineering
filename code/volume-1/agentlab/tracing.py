"""Prints each agent run's trace in the terminal, as a tree with one line per span."""

import json
from collections.abc import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

WIDTH = 60


def _short(text: str) -> str:
    return text if len(text) <= WIDTH else text[: WIDTH - 3] + "..."


class SpanTreePrinter(SpanExporter):
    """An OpenTelemetry span exporter that prints a trace once its top-level span has finished."""

    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.spans.extend(spans)
        for root in [span for span in spans if span.parent is None]:
            self._print(root, depth=0)
        return SpanExportResult.SUCCESS

    def _print(self, span: ReadableSpan, depth: int) -> None:
        attributes = dict(span.attributes or {})
        operation = attributes.get("gen_ai.operation.name", span.name)
        seconds = (span.end_time - span.start_time) / 1e9
        # The full span name ends with the model's name; the operation alone keeps the printout provider-neutral.
        line = f"{'    ' * depth}{operation:<12} {seconds:5.2f} s"
        if operation == "invoke_agent":
            line += (
                f"  {attributes.get('gen_ai.agent.name', '')}: read {attributes.get('gen_ai.usage.input_tokens', 0)} tokens,"
                f" wrote {attributes.get('gen_ai.usage.output_tokens', 0)} in total"
            )
        if operation == "chat":
            finish = json.loads(attributes.get("gen_ai.response.finish_reasons", "[]"))
            line += (
                f"  read {attributes.get('gen_ai.usage.input_tokens', 0):>5} tokens,"
                f" wrote {attributes.get('gen_ai.usage.output_tokens', 0):>4}, then {', '.join(finish)}"
            )
        if operation == "execute_tool":
            line += f"  {attributes.get('gen_ai.tool.name')}({attributes.get('gen_ai.tool.call.arguments', '')})"
            if "gen_ai.tool.call.result" in attributes:
                line += f"\n{'    ' * (depth + 1)}{'':<12}          -> {_short(attributes['gen_ai.tool.call.result'])}"
        print(line)
        children = [s for s in self.spans if s.parent is not None and s.parent.span_id == span.context.span_id]
        for child in sorted(children, key=lambda s: s.start_time):
            self._print(child, depth + 1)
