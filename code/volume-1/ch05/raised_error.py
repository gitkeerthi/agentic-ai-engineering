"""Chapter 5 demo: the document store is down, and the tool lets the error reach the framework."""

import asyncio

from cobalt import TOOLS, store
from investigate import TASK, investigator, show

store.behavior = "down"
agent = investigator(TOOLS)
print(f"Task: {TASK}  (the document store is down)\n")
show(asyncio.run(agent.run(TASK)))
