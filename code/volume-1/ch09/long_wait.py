"""Chapter 9 demo: the loop's time limit, when the approval takes longer than the limit.

The run's tool loop has max_duration_seconds=30, and the analyst answers 35 seconds after the request.
--harness adds the framework's ToolApprovalMiddleware, which keeps the loop's budget in the session.
"""

import argparse
import asyncio
import time

from agent_framework import ToolApprovalMiddleware

import cobalt
from investigate import TASK, answer, investigator, run_args, show

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--harness", action="store_true")
args = parser.parse_args()


async def main() -> None:
    cobalt.reset(note=True)
    agent = investigator(middleware=[ToolApprovalMiddleware()] if args.harness else None)
    agent.client.function_invocation_configuration["max_duration_seconds"] = 30
    session = agent.create_session()
    started = time.monotonic()
    result = await agent.run(TASK, session=session, function_invocation_kwargs=run_args())
    request = result.user_input_requests[0]
    print(f"Requested after {time.monotonic() - started:.0f} s: {request.function_call.arguments}")
    await asyncio.sleep(35)  # ①
    print(f"The analyst approves {time.monotonic() - started:.0f} s after the run started.\n")
    show(await agent.run(answer(request, True), session=session, function_invocation_kwargs=run_args()))
    print(f"\n{cobalt.where()}")


asyncio.run(main())
