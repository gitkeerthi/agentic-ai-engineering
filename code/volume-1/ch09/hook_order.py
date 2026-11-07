"""Chapter 9 demo: where an Agent Hooks deny lands, for a tool that needs approval (experimental).

The interceptor denies every refiling, as a freeze on refilings would. The program shows when the
person is asked, and when the hook runs.
"""

import asyncio
import warnings

from agent_framework import create_agent_hooks_middleware
from agent_hooks import Verdict

import cobalt
from investigate import TASK, answer, investigator, run_args, show

warnings.filterwarnings("ignore", message=".*experimental.*")


class RefilingFreeze:
    def intercept(self, context) -> Verdict:
        if context["interception_point"] == "pre_tool_call" and context["tool_call"]["name"] == "refile_document":
            print("  hook  pre_tool_call refile_document: deny")
            return Verdict.deny(reason="refilings are frozen")
        return Verdict.allow()


async def main() -> None:
    cobalt.reset(note=True)
    agent = investigator(middleware=[create_agent_hooks_middleware({"freeze": RefilingFreeze()})])
    session = agent.create_session()
    result = await agent.run(TASK, session=session, function_invocation_kwargs=run_args())
    print(f"The run returned {len(result.user_input_requests)} approval request(s). The analyst approves.\n")
    show(await agent.run(answer(result.user_input_requests[0], True), session=session, function_invocation_kwargs=run_args()))
    print(f"\n{cobalt.where()}")


asyncio.run(main())
