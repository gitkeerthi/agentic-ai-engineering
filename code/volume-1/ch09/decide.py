"""Chapter 9 demo: answer a saved approval request, in a separate process, any time later.

    uv run python ch09/decide.py <request-id> --approve
    uv run python ch09/decide.py <request-id> --reject
"""

import argparse
import asyncio
import json

from agent_framework import AgentSession, Content

import cobalt
from investigate import PENDING, answer, investigator, run_args, show

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("request_id")
decision = parser.add_mutually_exclusive_group(required=True)
decision.add_argument("--approve", action="store_true")
decision.add_argument("--reject", action="store_true")
args = parser.parse_args()

saved = json.loads((PENDING / f"{args.request_id}.json").read_text())
session = AgentSession.from_dict(saved["session"])  # ①
request = Content.from_dict(saved["request"])
print(f"Request: {request.function_call.name}({request.function_call.arguments})")
print(f"Decision: {'approved' if args.approve else 'rejected'}\n")

agent = investigator()
result = asyncio.run(agent.run(answer(request, args.approve), session=session,
                               function_invocation_kwargs=run_args()))  # ②
show(result)
print(f"\n{cobalt.where()}")
