"""Chapter 8 demo: Chapter 4's run at a loop limit of 2, without and with the report middleware (--report).
--failing-tools makes every tool call fail, so the run ends at the framework's error limit instead.

Runs in a session, and prints what the session stored, so you can see whether the report request was kept.
"""

import argparse
import asyncio

from agent_framework import FunctionInvocationContext, function_middleware

from investigate import TASK, investigator
from middleware import limit_report

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--report", action="store_true")
parser.add_argument("--failing-tools", action="store_true")
args = parser.parse_args()



@function_middleware
async def failing(context: FunctionInvocationContext, call_next) -> None:
    raise RuntimeError("tool unavailable")


middleware = [limit_report] if args.report else []
if args.failing_tools:
    middleware.append(failing)
agent = investigator(max_iterations=9 if args.failing_tools else 2, middleware=middleware)
session = agent.create_session()
result = asyncio.run(agent.run(TASK, session=session))
print(result.messages[-1].text)
print(f"\nlimit_reached: {result.additional_properties.get('limit_reached', False)}")
stored = session.state["in_memory"]["messages"]
print(f"Session stored {len(stored)} messages; user messages: {[m.text[:60] for m in stored if m.role == 'user']}")
