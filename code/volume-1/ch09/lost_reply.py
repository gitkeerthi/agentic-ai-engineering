"""Chapter 9 demo: the store refiles DOC-5531 and its reply is lost. What does the caller get?

No model call: a scripted client asks for the refiling, and the program approves it, so the framework runs
the real tool. By default the approval carries its ID, as the refiling gate sends it, and the tool retries
with that ID as its key. --no-key approves the way decide.py does, with no ID, so the tool tries once.
--retry-without-key calls the store's retry wrapper with no key, as a tool that retried anyway would;
--no-version-check makes the store ignore expected_version.
"""

import argparse
import asyncio
import json
import logging

from agent_framework import Agent

import cobalt
from investigate import answer
from scripted import ScriptedClient

logging.getLogger("agent_framework").setLevel(logging.ERROR)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--no-key", action="store_true")
parser.add_argument("--retry-without-key", action="store_true")
parser.add_argument("--no-version-check", action="store_true")
args = parser.parse_args()
cobalt.COMPARE_VERSIONS = not args.no_version_check
ARGUMENTS = {"document_id": "DOC-5531", "customs_case": "RTM-88213", "expected_version": 1}


async def approved_tool_call() -> str:
    """Approve the scripted request and return the tool's result, as the model receives it."""
    agent = Agent(ScriptedClient([("refile_document", ARGUMENTS, "c1"), "done"]), "Investigate.",
                  tools=[cobalt.refile_document])
    session = agent.create_session()
    request = (await agent.run("Refile DOC-5531.", session=session)).user_input_requests[0]
    cobalt.drop_next_reply()  # ①
    values = {} if args.no_key else {  # ② as the gate sends them
        "approval_id": request.id, "approved_by": "lead-031",
        "approved_arguments": ARGUMENTS}
    result = await agent.run(answer(request, True), session=session,
                             function_invocation_kwargs=values)
    return next(c.result for m in result.messages for c in m.contents if c.type == "function_result")


cobalt.reset()
if args.retry_without_key:
    cobalt.drop_next_reply()
    retried = cobalt.refile_with_retries(**ARGUMENTS, key=None)
    print(f"A caller that retries without a key gets: {retried}")  # ③
else:
    result = asyncio.run(approved_tool_call())
    print(f"The tool's result, as the model gets it: {result if isinstance(result, str) else json.dumps(result)}")
print(f"Filings at customs: {[f['filing'] + ' ' + f['document_id'] for f in cobalt.load()['filings']]}")
