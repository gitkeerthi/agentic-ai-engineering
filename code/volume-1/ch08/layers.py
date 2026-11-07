"""Chapter 8 demo: the three kinds of middleware, how often each runs in one run, and in what order."""

import asyncio

from agent_framework import AgentContext, ChatContext, FunctionInvocationContext, agent_middleware, chat_middleware, function_middleware

from investigate import TASK, investigator

counts = {"agent": 0, "chat": 0, "function": 0}


@agent_middleware
async def on_run(context: AgentContext, call_next) -> None:
    counts["agent"] += 1
    print(f"agent    in   {len(context.messages)} input message(s)")
    await call_next()
    print(f"agent    out  result: {len(context.result.messages)} messages")


@agent_middleware
async def on_this_run(context: AgentContext, call_next) -> None:
    print("run      in   (registered for this run only)")
    await call_next()
    print("run      out")


@chat_middleware
async def on_model_call(context: ChatContext, call_next) -> None:
    counts["chat"] += 1
    print(f"chat     in   call {counts['chat']}: {len(context.messages)} messages, tool_choice={context.options.get('tool_choice')}")
    await call_next()
    asked = [c.name for m in context.result.messages for c in m.contents if c.type == "function_call"]
    print(f"chat     out  call {counts['chat']}: asks for {asked or 'no tools'}")


@function_middleware
async def on_tool_call(context: FunctionInvocationContext, call_next) -> None:
    counts["function"] += 1
    print(f"function in   {context.function.name}({dict(context.arguments)})")  # ①
    await call_next()  # ②
    print(f"function out  {context.function.name}")  # ③


agent = investigator(middleware=[on_run, on_model_call, on_tool_call])
asyncio.run(agent.run(TASK, middleware=[on_this_run]))
print(f"\nIn one run: agent middleware {counts['agent']}, chat middleware {counts['chat']}, function middleware {counts['function']}")
