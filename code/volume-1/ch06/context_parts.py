"""Chapter 6 demo: what one model call contains, and what each part costs in tokens.

The same follow-up is sent four times, adding one part each time. For each, we read the input tokens the provider
reports for the run's first model call, which is the assembled request.

    uv run python ch06/context_parts.py
"""

import asyncio

from agent_framework import Agent

from agentlab.llm import make_client
from cobalt import TOOLS
from investigate import FIRST_TASK, FOLLOW_UP, INSTRUCTIONS, calls, investigator, meter


def bare_agent(instructions: str | None = None, tools: list | None = None) -> Agent:
    client = make_client()
    client.function_invocation_configuration["max_iterations"] = 1  # only the first call is measured
    return Agent(client, instructions, tools=tools, middleware=[meter])


async def first_call_input(agent: Agent, **run_settings) -> int:
    first = len(calls)
    await agent.run(FOLLOW_UP, **run_settings)
    return calls[first]["input"]


async def main() -> None:
    # The history: one investigation in a session, as in session.py.
    agent = investigator()
    session = agent.create_session()
    await agent.run(FIRST_TASK, session=session)
    stored = len(session.state["in_memory"]["messages"])

    task_only = await first_call_input(bare_agent())
    with_instructions = await first_call_input(bare_agent(INSTRUCTIONS))
    with_tools = await first_call_input(bare_agent(INSTRUCTIONS, TOOLS))
    with_history = await first_call_input(agent, session=session)

    print(f"Follow-up: {FOLLOW_UP}\n")
    print(f"{'Part':<36}{'Tokens':>8}")
    print(f"{'Task (with the message format)':<36}{task_only:>8}")
    print(f"{'Instructions':<36}{with_instructions - task_only:>8}")
    print(f"{'Tool definitions (4 tools)':<36}{with_tools - with_instructions:>8}")
    print(f"{f'History ({stored} stored messages)':<36}{with_history - with_tools:>8}")
    print(f"{'Whole call':<36}{with_history:>8}")


asyncio.run(main())
