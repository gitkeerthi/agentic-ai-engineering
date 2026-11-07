"""Chapter 12 demo: a recorded reply replayed after a one-phrase change to the agent's instructions. No model call.

    uv run python ch12/replay_mismatch.py

The recording answers only the request it was made for. With the instructions changed, the request's body
changes, the cassette has no reply for it, and the run fails instead of passing on a reply the model never
gave to these instructions.
"""

import asyncio
from pathlib import Path

import vcr

import agentlab.llm
import steps

agentlab.llm.record = (
    lambda *usage: None
)  # a replayed reply costs nothing: don't log it as a call

CASSETTE = (
    Path(__file__).parent
    / "cassettes/test_recorded/test_case_set_replayed[SH-4471].yaml"
)
replay = vcr.VCR(record_mode="none", match_on=["method", "uri", "body"])


async def investigate() -> str:
    with replay.use_cassette(str(CASSETTE)):
        try:
            [output] = (
                await steps.investigation(steps.interpreter()).run("SH-4471")
            ).get_outputs()
            return f"replayed: {output.status}"
        except Exception as error:
            cause = error.__cause__ or error
            return (
                f"failed: {type(error).__name__}, caused by {type(cause).__name__}"
            )


print("Instructions as recorded:", asyncio.run(investigate()))
steps.INSTRUCTIONS = steps.INSTRUCTIONS.replace(
    "Find what is holding", "Work out what is holding"
)
print("One phrase changed:      ", asyncio.run(investigate()))
