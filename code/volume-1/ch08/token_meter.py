"""Chapter 8 demo: chat middleware that meters each model call's tokens as the run goes."""

import asyncio

from agent_framework import ChatContext, chat_middleware

from investigate import TASK, investigator

calls = []


@chat_middleware
async def meter(context: ChatContext, call_next) -> None:
    await call_next()  # ①
    usage = context.result.usage_details or {}  # ②
    calls.append(usage)
    print(f"Call {len(calls)}: input {usage.get('input_token_count', 0):>5}  "
          f"cached {usage.get('cache_read_input_token_count', 0):>5}  "
          f"output {usage.get('output_token_count', 0):>4}")


agent = investigator(middleware=[meter])
result = asyncio.run(agent.run(TASK))
total = sum(u.get("input_token_count", 0) + u.get("output_token_count", 0) for u in calls)
print(f"\nMetered total: {total} tokens in {len(calls)} calls")
print(f"The response's own total: {result.usage_details.get('total_token_count')}")
