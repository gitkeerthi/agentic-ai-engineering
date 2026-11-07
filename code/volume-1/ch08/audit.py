"""Chapter 8 demo: one audit middleware for every tool, with the caller's identity and personal data redacted.

--store-down makes every audit write fail. --naive uses a first version that writes after the call and
lets the error escape. --no-user runs without passing who the run is for.
"""

import argparse
import asyncio
from datetime import datetime, timezone

from agent_framework import FunctionInvocationContext, function_middleware

import audit_store
from cobalt import TOOLS, get_customer_contact
from investigate import WITH_UPDATE, investigator, run_args, show
from middleware import audit_trail, redact, result_data

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--store-down", action="store_true")
parser.add_argument("--naive", action="store_true")
parser.add_argument("--no-user", action="store_true")
args = parser.parse_args()

executed = []  # every tool call that actually ran


@function_middleware
async def count_executions(context: FunctionInvocationContext, call_next) -> None:
    await call_next()
    executed.append(context.function.name)


@function_middleware
async def naive_audit(context: FunctionInvocationContext, call_next) -> None:
    await call_next()
    audit_store.write({
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": context.kwargs.get("user_id"),
        "tool": context.function.name,
        "arguments": dict(context.arguments),
        "result": redact(result_data(context.result)),
    })


audit_store.clear()
audit_store.state["down"] = args.store_down
agent = investigator(tools=[*TOOLS, get_customer_contact], middleware=[naive_audit if args.naive else audit_trail, count_executions])
print(f"Task: {WITH_UPDATE}\n")
try:
    runtime_values = {} if args.no_user else run_args()
    run = agent.run(WITH_UPDATE, function_invocation_kwargs=runtime_values)
    result = asyncio.run(run)
    show(result)
except Exception as error:
    print(f"Run raised {type(error).__name__}: {error}")
print(f"\nTool calls that ran: {len(executed)} {executed}")
audit_store.show()
