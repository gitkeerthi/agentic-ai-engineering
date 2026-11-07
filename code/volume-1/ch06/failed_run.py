"""Chapter 6 demo: the model service fails on the fourth model call of a run. What does the session keep,
and can the same task run again in that session?

    uv run python ch06/failed_run.py
    uv run python ch06/failed_run.py --per-call
    uv run python ch06/failed_run.py --per-call --repair
"""

import argparse
import asyncio

from agent_framework import ChatContext, chat_middleware

from investigate import FIRST_TASK, calls, investigator, show

model_calls = 0


@chat_middleware
async def fail_fourth_call(context: ChatContext, call_next) -> None:
    global model_calls
    model_calls += 1
    if model_calls == 4:
        raise ConnectionError("model service: connection reset")
    await call_next()


def drop_unanswered_tool_requests(messages: list) -> None:
    """Drop tool requests at the end of the history that have no stored results."""
    while messages and messages[-1].role == "assistant" and any(
        c.type == "function_call" for c in messages[-1].contents
    ):
        messages.pop()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--per-call", action="store_true", help="save the history after every model call")
parser.add_argument("--repair", action="store_true", help="drop unanswered tool requests before running again")
options = parser.parse_args()


async def main() -> None:
    agent = investigator(require_per_service_call_history_persistence=options.per_call)
    agent.middleware.append(fail_fourth_call)
    session = agent.create_session()
    print(f"Task: {FIRST_TASK}  (history saved {'after every model call' if options.per_call else 'once, after the run'})\n")
    try:
        await agent.run(FIRST_TASK, session=session)
    except ConnectionError as error:
        print(f"The run failed on model call {model_calls}: {error}")

    messages = session.state.get("in_memory", {}).get("messages", [])
    print(f"\nThe session holds {len(messages)} messages:")
    for message in messages:
        print(f"  {message.role}: {', '.join(c.type for c in message.contents)}")
    if options.repair:
        drop_unanswered_tool_requests(messages)
        print(f"After the repair: {len(messages)} messages")

    print("\nThe service is back. The same task runs again in the same session.\n")
    calls_before = len(calls)
    try:
        show(await agent.run(FIRST_TASK, session=session))
        print(f"\nModel calls in the second run: {len(calls) - calls_before}")
    except Exception as error:
        message = str(error).split("Error code: ")[-1].split(" (request_id")[0]
        print(f"The second run failed: {message}")


asyncio.run(main())
