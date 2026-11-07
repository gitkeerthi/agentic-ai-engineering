"""Chapter 8 demo: checks of the chapter's middleware with a scripted client. No model call.

1. outcome() on the endings of `limit_report.py --report --failing-tools`: every tool call fails, and the
   model gives up after two failures, or the run reaches the framework's limit of three failing rounds;
   then the store-busy ending that RepeatStop makes, an ordinary answer, and an Agent Hooks policy
   deny at each tool point, after which the model answers
2. audit_trail on an ordinary call, and when a middleware inside it skips the tool without setting a result
3. MiddlewareTermination without a substitute result, in chat and in agent middleware
4. TokenBudget and BudgetGuard when each model call reports 1,100 tokens, and when it reports none
"""

import asyncio
import json
import logging
import sys
import tempfile
import warnings
from pathlib import Path

from agent_framework import (
    Agent,
    MiddlewareTermination,
    create_agent_hooks_middleware,
    agent_middleware,
    chat_middleware,
    function_middleware,
)

import audit_store
import cobalt
from agent_hooks import Verdict

from investigate import INSTRUCTIONS, TASK, outcome, run_args
from middleware import BudgetGuard, RepeatStop, TokenBudget, audit_trail, limit_report
from scripted import ScriptedClient

warnings.filterwarnings("ignore", message=".*experimental.*")

logging.getLogger("agent_framework").setLevel(logging.CRITICAL)
logging.basicConfig(stream=sys.stdout, format="  alert: %(message)s")
audit_store.PATH = Path(tempfile.mkdtemp()) / "audit.jsonl"  # leave the lab's own log alone


@function_middleware
async def failing(context, call_next) -> None:
    raise RuntimeError("tool unavailable")  # as in limit_report.py --failing-tools


@function_middleware
async def skips_the_tool(context, call_next) -> None:
    return  # doesn't call call_next(), and sets no result


class DenyAt:
    """Agent Hooks interceptor: a policy deny for every tool call at one tool point."""

    def __init__(self, point: str) -> None:
        self.point = point

    def intercept(self, context) -> Verdict:
        if context["interception_point"] == self.point:
            return Verdict.deny(reason="case lookups frozen")
        return Verdict.allow()


def status(call_id: str) -> tuple:
    return ("get_shipment_status", {"shipment_id": "SH-4471"}, call_id)


def search(call_id: str, reverse: bool = False) -> tuple:
    arguments = {"shipment_id": "SH-4471", "document_type": "commercial invoice"}
    if reverse:
        arguments = dict(reversed(arguments.items()))
    return ("find_document", arguments, call_id)


class MeteredClient(ScriptedClient):
    """A scripted client whose every reply reports 1,000 input and 100 output tokens."""

    async def _inner_get_response(self, **kwargs):
        response = await super()._inner_get_response(**kwargs)
        response.usage_details = {"input_token_count": 1000, "output_token_count": 100}
        return response


async def run(replies: list, middleware: list, run_middleware=None, tools=cobalt.TOOLS,
              client_type=ScriptedClient):
    client = client_type(replies)
    agent = Agent(client, INSTRUCTIONS, tools=tools, middleware=middleware)
    result = await agent.run(TASK, middleware=run_middleware, function_invocation_kwargs=run_args())
    return client, result


async def main() -> None:
    print("1. How outcome() reads each ending")
    endings = [
        ("Two failures, then the model gives up",
         [status("c1"), status("c2"), "Cause: Unknown. The lookup failed twice."],
         [limit_report, failing], None),
        ("Three failures, the error limit, the tools-off call",
         [status("c1"), status("c2"), status("c3"), "Cause: Unknown. Still unknown: everything."],
         [limit_report, failing], None),
        ("Store busy, the third identical search",
         [search("c1"), search("c2", reverse=True), search("c3", reverse=True)],
         [audit_trail, limit_report], [RepeatStop()]),
        ("One lookup, then an answer",
         [status("c1"), "Cause: The shipment is held."],
         [audit_trail, limit_report], None),
        ("A pre_tool_call deny, then an answer",
         [status("c1"), "Cause: Unknown."],
         [create_agent_hooks_middleware({"freeze": DenyAt("pre_tool_call")})], None),
        ("A post_tool_call deny, then an answer",
         [status("c1"), "Cause: Unknown."],
         [create_agent_hooks_middleware({"freeze": DenyAt("post_tool_call")})], None),
    ]
    for name, replies, middleware, run_middleware in endings:
        cobalt.reset()
        if name.startswith("Store busy"):
            cobalt.make_store_busy()
        _, result = await run(replies, middleware, run_middleware)
        print(f"  {name}: {outcome(result)}")
    cobalt.reset()

    print("\n2. audit_trail on an ordinary call, then when a middleware inside it skips the tool")
    audit_store.clear()
    contact = ("get_customer_contact", {"shipment_id": "SH-4471"}, "c1")
    await run([contact, "Done."], [audit_trail], tools=[cobalt.get_customer_contact])
    for line in audit_store.PATH.read_text().splitlines():
        record = json.loads(line)
        print(f"  {record['phase']}: {record.get('result', record['arguments'])}")
    audit_store.clear()
    client, result = await run([status("c1"), "Done."], [audit_trail, skips_the_tool])
    messages, _ = client.sent[-1]
    sent = [str(c.result) for m in messages for c in m.contents if c.type == "function_result"]
    print(f"  The model was sent: {sent}")
    records = audit_store.PATH.read_text().splitlines() if audit_store.PATH.exists() else []
    print(f"  Audit records, by phase: {[json.loads(r)['phase'] for r in records]}")

    print("\n3. MiddlewareTermination with no substitute in context.result")

    @chat_middleware
    async def chat_stop(context, call_next) -> None:
        raise MiddlewareTermination("policy stop")

    @agent_middleware
    async def agent_stop(context, call_next) -> None:
        raise MiddlewareTermination("policy stop")

    for name, middleware in [("Chat middleware", chat_stop), ("Agent middleware", agent_stop)]:
        try:
            _, result = await run(["Never sent."], [middleware])
            print(f"  {name}: agent.run() returned {result!r}")
        except Exception as error:
            print(f"  {name}: agent.run() raised {type(error).__name__}: {error}")

    print("\n4. A budget of 2,000 tokens; four lookups, then an answer")
    replies = [status("c1"), status("c2"), status("c3"), status("c4"), "Cause: found."]
    for client_type in (MeteredClient, ScriptedClient):
        usage = "1,100 tokens a call" if client_type is MeteredClient else "no usage reported"
        _, result = await run(list(replies), [], [TokenBudget(2000)], client_type=client_type)
        print(f"  TokenBudget, {usage}: {result.text!r}")
        hooks = create_agent_hooks_middleware({"budget": BudgetGuard(2000)})
        try:
            _, result = await run(list(replies), [hooks], client_type=client_type)
            print(f"  BudgetGuard, {usage}: {result.text!r}")
        except Exception as error:
            print(f"  BudgetGuard, {usage}: {type(error).__name__}: {error}")


asyncio.run(main())
