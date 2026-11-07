"""Chapter 4 demo: the investigation agent with tracing on, so the framework's hidden loop is visible."""

import argparse
import asyncio

from agent_framework import Agent
from agent_framework.observability import configure_otel_providers
from opentelemetry import trace

from agentlab.tracing import SpanTreePrinter
from cobalt import TOOLS
from investigate import INSTRUCTIONS, agent

# Chapter 3's claim-checking rule (its Example 3-11), word for word. Off unless --check-claims is given.
CHECK_CLAIMS = """

Before investigating, check the task's claims against the systems. If the systems
contradict the task (for example, the shipment is not late), say so and stop."""

# Sensitive data puts prompts, replies, tool arguments and results in the spans. Development only.
configure_otel_providers(exporters=[SpanTreePrinter()], enable_sensitive_data=True)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("task", nargs="?", default="Shipment SH-4471 is three days late. Find out why.")
parser.add_argument("--max-iterations", type=int, help="the limit on rounds of tool calls (investigate.py sets 9)")
parser.add_argument("--check-claims", action="store_true", help="add Chapter 3's claim-checking rule to the instructions")
args = parser.parse_args()
if args.check_claims:
    agent = Agent(agent.client, INSTRUCTIONS + CHECK_CLAIMS, name="investigator", tools=TOOLS)
if args.max_iterations:
    agent.client.function_invocation_configuration["max_iterations"] = args.max_iterations
print(f"Task: {args.task}\n")
result = asyncio.run(agent.run(args.task))
print(result.messages[-1].text)

print("\nTrace:")
trace.get_tracer_provider().force_flush()  # spans are exported in batches; send this run's now
