"""Chapter 10: ask for JSON-object output, then validate it as a Finding."""

import asyncio

from agent_framework import Agent

from agentlab.llm import make_client
from contracts import Finding
from cobalt import TOOLS

TASK = """Investigate shipment SH-4471 using the available tools. Return one JSON
object with status, cause, evidence_document_ids, and recommended_action.
Use null for unknown values. Do not claim to have changed any record."""

agent = Agent(
    make_client(),
    "You investigate Cobalt Freight shipment exceptions. Use the available tools "
    "to check evidence. Return only the requested JSON object; do not invent evidence.",
    name="finding-agent",
    tools=TOOLS,
)


async def main() -> None:
    result = await agent.run(TASK, options={"response_format": {"type": "json_object"}})
    finding = Finding.model_validate_json(result.text)
    print(finding.model_dump_json(indent=2))


asyncio.run(main())
