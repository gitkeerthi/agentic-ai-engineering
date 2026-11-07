"""Chapter 8 demo: the document store answers "busy" to every search; RepeatStop ends the run on the third identical request."""

import asyncio

import cobalt
from investigate import TASK, investigator, show
from middleware import RepeatStop

cobalt.make_store_busy()
agent = investigator()
result = asyncio.run(agent.run(TASK, middleware=[RepeatStop()]))  # a fresh counter for this run
show(result)
last = result.messages[-1]
print(f"\nfinish_reason: {result.finish_reason}; last message: {last.role}, {[c.type for c in last.contents]}")
print(f"Tool result in it: {[c.result for c in last.contents if c.type == 'function_result']}")
