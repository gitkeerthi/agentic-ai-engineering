"""Chapter 8 demo: a run's reply withheld after the run, and what the session stores.

By default, agent middleware replaces the result after the run. --hooks uses an Agent Hooks interceptor
that denies the output instead (experimental; needs agent-hooks-sdk).
"""

import argparse
import asyncio
import warnings

from agent_framework import AgentContext, AgentResponse, Message, agent_middleware, create_agent_hooks_middleware
from agent_hooks import Verdict

from investigate import investigator

warnings.filterwarnings("ignore", message=".*experimental.*")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--hooks", action="store_true")
args = parser.parse_args()


@agent_middleware
async def replace(context: AgentContext, call_next) -> None:
    await call_next()
    reply = Message("assistant", ["[withheld by policy]"])
    context.result = AgentResponse(messages=[reply])


class WithholdOutput:
    def intercept(self, context) -> Verdict:
        if context["interception_point"] == "output" and "pineapple" in str(context["target"]).lower():
            return Verdict.deny(reason="withheld by policy")
        return Verdict.allow()


middleware = [create_agent_hooks_middleware({"withhold": WithholdOutput()})] if args.hooks else [replace]
agent = investigator(tools=[], middleware=middleware)
session = agent.create_session()
try:
    result = asyncio.run(agent.run("Say the word 'pineapple' and nothing else.", session=session))
    print(f"caller got: {result.text}")
except Exception as error:
    print(f"caller got: {type(error).__name__}: {error}")
print(f"session stored: {[(m.role, m.text) for m in session.state.get('in_memory', {}).get('messages', [])]}")
