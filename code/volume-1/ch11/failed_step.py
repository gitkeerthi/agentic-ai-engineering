"""Chapter 11 check: what the caller sees when a step fails. No model call.

Two failures, each streamed so the run's events show: the document store answers every search with "busy", so
check_documents raises StoreUnavailable; then the agent step's model call fails, played by a scripted client
that raises a connection error.
"""

import asyncio

from cobalt import make_store_busy, reset
from scripted import ScriptedClient
from steps import interpreter, investigation


async def show(workflow) -> None:
    try:
        async for event in workflow.run("SH-4471", stream=True):
            if event.type in ("executor_failed", "failed"):
                error = f"{event.details.error_type}: {event.details.message}"
                print(f"{event.type:<18} {event.executor_id or '':<16} {error}")
            elif event.type == "status":
                print(f"{event.type:<18} {'':<16} {event.state}")
            elif event.type in ("executor_invoked", "started"):
                print(f"{event.type:<18} {event.executor_id or ''}")
    except Exception as error:
        print(f"\nThe caller receives: {type(error).__name__}: {error}\n")


async def main() -> None:
    print("1. The document store is busy\n")
    make_store_busy()
    await show(investigation(interpreter(ScriptedClient([]))))
    reset()

    print("2. The agent step's model call fails\n")
    model_down = ScriptedClient([ConnectionError("model endpoint unreachable")])
    await show(investigation(interpreter(model_down)))


asyncio.run(main())
