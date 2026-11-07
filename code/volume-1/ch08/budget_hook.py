"""Chapter 8 demo: the token budget as an Agent Hooks interceptor (experimental; needs agent-hooks-sdk).

--crash makes the interceptor raise on the first tool call, to show that Agent Hooks fails closed.
--evaluate-only records the verdicts without acting on them.
"""

import argparse
import asyncio
import warnings

from agent_framework import create_agent_hooks_middleware

from investigate import TASK, investigator, show
from middleware import BudgetGuard

warnings.filterwarnings("ignore", message=".*experimental.*")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--budget", type=int, default=3000)
parser.add_argument("--crash", action="store_true")
parser.add_argument("--evaluate-only", action="store_true")
args = parser.parse_args()


class CrashingGuard(BudgetGuard):
    def intercept(self, context):
        if context["interception_point"] == "pre_tool_call":
            raise RuntimeError("budget guard crashed")
        return super().intercept(context)


def log(record) -> None:
    reason = f"  ({record.verdict.reason})" if record.verdict.reason else ""
    print(f"  hook  {record.interception_point.value:<16} {record.verdict.decision.value}{reason}")


guard = CrashingGuard(args.budget) if args.crash else BudgetGuard(args.budget)
mode = "evaluate_only" if args.evaluate_only else "enforce"
hooks = create_agent_hooks_middleware({"budget": guard}, mode=mode, record_sink=log)
agent = investigator(middleware=[hooks])  # the bundle goes first
try:
    show(asyncio.run(agent.run(TASK)))
except Exception as error:
    print(f"\nRun raised {type(error).__name__}: {error}")
