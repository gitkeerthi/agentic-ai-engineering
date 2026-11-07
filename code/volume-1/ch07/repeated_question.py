"""Chapter 7 demo: the same question asked twice in one session, and what the framework's history provider stores.

    uv run python ch07/repeated_question.py
"""

import asyncio

from agent_framework import Agent

from agentlab.llm import make_client

QUESTIONS = ["Name a port in the Netherlands.", "Name one in Belgium.", "Name a port in the Netherlands."]


async def main() -> None:
    agent = Agent(make_client(), "Answer in five words or fewer.")
    session = agent.create_session()
    for question in QUESTIONS:
        result = await agent.run(question, session=session)
        print(f"Run: {question}  Answer: {result.text}")
    print("\nStored history:")
    for message in session.state["in_memory"]["messages"]:
        print(f"  {message.role:<9} {message.text!r}")


asyncio.run(main())
