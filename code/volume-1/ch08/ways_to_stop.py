"""Chapter 8 demo: three ways middleware can stop, what the caller gets, and what the session keeps.

--how terminate | failure | plain picks the exception. Function middleware (the default) raises on every
tool call; --layer chat raises before every model call, --layer agent before the run.
"""

import argparse
import asyncio

from agent_framework import (
    AgentContext,
    AgentResponse,
    ChatContext,
    ChatResponse,
    FunctionInvocationContext,
    Message,
    MiddlewareFailure,
    MiddlewareTermination,
    agent_middleware,
    chat_middleware,
    function_middleware,
)

from investigate import TASK, investigator

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--how", choices=["terminate", "failure", "plain"], required=True)
parser.add_argument("--layer", choices=["function", "chat", "agent"], default="function")
args = parser.parse_args()


@function_middleware
async def stop(context: FunctionInvocationContext, call_next) -> None:
    if args.how == "terminate":
        raise MiddlewareTermination("policy stop", result="Stopped by policy.")  # ①
    if args.how == "failure":
        raise MiddlewareFailure("policy check failed")  # ②
    raise RuntimeError("policy check crashed")  # ③


@chat_middleware
async def stop_model_call(context: ChatContext, call_next) -> None:
    if args.how == "terminate":
        context.result = ChatResponse(messages=[Message("assistant", ["Stopped by policy."])])
        raise MiddlewareTermination("policy stop")
    if args.how == "failure":
        raise MiddlewareFailure("policy check failed")
    raise RuntimeError("policy check crashed")


@agent_middleware
async def stop_run(context: AgentContext, call_next) -> None:
    if args.how == "terminate":
        context.result = AgentResponse(messages=[Message("assistant", ["Stopped by policy."])])
        raise MiddlewareTermination("policy stop")
    if args.how == "failure":
        raise MiddlewareFailure("policy check failed")
    raise RuntimeError("policy check crashed")


agent = investigator(middleware=[{"function": stop, "chat": stop_model_call, "agent": stop_run}[args.layer]])
session = agent.create_session()
try:
    result = asyncio.run(agent.run(TASK, session=session))
    print(f"Caller gets an AgentResponse: finish_reason {result.finish_reason}, {len(result.messages)} messages")
    for message in result.messages:
        parts = [c.type if c.type != "function_result" else f"function_result({c.result!r})" for c in message.contents]
        print(f"  {message.role:<9} {parts}  {(message.text or '')[:90]!r}")
    print(f"result.text: {result.text[:120]!r}")
except Exception as error:
    print(f"Caller gets an exception: {type(error).__name__}: {error}")
stored = session.state.get("in_memory", {}).get("messages", [])
print(f"Session stored {len(stored)} messages: {[m.role for m in stored]}")
