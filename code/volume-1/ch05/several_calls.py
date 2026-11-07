"""Chapter 5 demo: the model asks for several tools in one reply. What do the two settings change?

Every system takes two seconds to answer, so the times show whether the calls in one reply ran together.
"""

import argparse
import asyncio
import time

from agent_framework import function_middleware

import cobalt
from cobalt import TOOLS, customs, store, tracker
from investigate import TASK, investigator, show

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "setting",
    choices=["default", "one-at-a-time", "one-per-reply"],
    help="default: both settings on; one-at-a-time: allow_concurrent_invocation off; "
    "one-per-reply: allow_multiple_tool_calls off",
)
setting = parser.parse_args().setting

cobalt.SLOW_SECONDS = 2
for system in (tracker, customs, store):
    system.behavior = "slow"

timings = []  # (tool, began, ended), in seconds from the start of the run


@function_middleware
async def timed(context, call_next):
    began = time.monotonic() - start
    await call_next()
    timings.append((context.function.name, began, time.monotonic() - start))


agent = investigator(TOOLS)
options = {}
if setting == "one-at-a-time":
    config = agent.client.function_invocation_configuration
    config["allow_concurrent_invocation"] = False
if setting == "one-per-reply":
    options["allow_multiple_tool_calls"] = False

print(f"Task: {TASK}  (setting: {setting}; each system takes {cobalt.SLOW_SECONDS} seconds to answer)\n")
start = time.monotonic()
result = asyncio.run(agent.run(TASK, options=options, middleware=[timed]))
show(result)

print("\nTool calls, with when each began and ended (seconds from the start of the run):")
for name, began, ended in sorted(timings, key=lambda t: t[1]):
    print(f"  {name:<25} {began:5.1f} to {ended:5.1f}")
replies = [sum(c.type == "function_call" for c in m.contents) for m in result.messages if m.role == "assistant"]
asking = [n for n in replies if n]
print(f"Replies that asked for tools: {len(asking)}. Replies that asked for more than one: {sum(n > 1 for n in asking)}.")
