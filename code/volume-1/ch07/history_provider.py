"""Chapter 7 demo: a history kept in a file by a history provider that repairs it when loading.
`fail` runs the investigation with the history saved after every model call, and the fourth model call fails.
`resume`, in a new process, loads the same session's history and runs the task again.

    uv run python ch07/history_provider.py fail
    uv run python ch07/history_provider.py resume
    uv run python ch07/history_provider.py resume --plain   # the framework's provider, without the repair
"""

import asyncio
import sys
from pathlib import Path

from agent_framework import AgentSession, ChatContext, FileHistoryProvider, chat_middleware

from investigate import FIRST_TASK, calls, investigator, show
from providers import RepairingFileHistory

FOLDER = Path(__file__).parent / "history"
SESSION_ID = "investigation-sh-4471"
model_calls = 0


@chat_middleware
async def fail_fourth_call(context: ChatContext, call_next) -> None:
    global model_calls
    model_calls += 1
    if model_calls == 4:
        raise ConnectionError("model service: connection reset")
    await call_next()


async def print_stored() -> None:
    messages = await FileHistoryProvider(FOLDER).get_messages(SESSION_ID)
    print(f"The file holds {len(messages)} messages:")
    for message in messages:
        print(f"  {message.role}: {', '.join(c.type for c in message.contents)}")


async def fail() -> None:
    (FOLDER / f"{SESSION_ID}.jsonl").unlink(missing_ok=True)
    agent = investigator(
        context_providers=[RepairingFileHistory(FOLDER)],
        require_per_service_call_history_persistence=True,
    )
    agent.middleware.append(fail_fourth_call)
    try:
        await agent.run(FIRST_TASK, session=AgentSession(session_id=SESSION_ID))
    except ConnectionError as error:
        print(f"The run failed on model call {model_calls}: {error}\n")
    await print_stored()


async def resume() -> None:
    provider = FileHistoryProvider(FOLDER) if "--plain" in sys.argv else RepairingFileHistory(FOLDER)
    await print_stored()
    agent = investigator(context_providers=[provider])
    print(f"\nThe service is back. The same task runs again in the same session, loaded by {type(provider).__name__}.\n")
    try:
        show(await agent.run(FIRST_TASK, session=AgentSession(session_id=SESSION_ID)))
        print(f"\nModel calls in this run: {len(calls)}")
    except Exception as error:
        message = str(error).split("Error code: ")[-1].split(" (request_id")[0]
        print(f"The run failed: {message}")


asyncio.run(fail() if sys.argv[1] == "fail" else resume())
