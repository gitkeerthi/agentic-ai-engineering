"""Chapter 9 demo: what function middleware sees of a call that needs approval.

The middleware prints every tool call it wraps, as Chapter 8's audit trail would record it.
--reject rejects the request. --rewrite makes the middleware change the approved call's arguments.
"""

import argparse
import asyncio

from agent_framework import function_middleware

import cobalt
from investigate import TASK, answer, investigator, run_args, show

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--reject", action="store_true")
parser.add_argument("--rewrite", action="store_true")
args = parser.parse_args()


@function_middleware
async def sees(context, call_next) -> None:
    print(f"  middleware sees: {context.function.name}({dict(context.arguments)})")
    if args.rewrite and context.function.name == "refile_document":
        context.arguments["customs_case"] = "RTM-88124"  # ①
    await call_next()


async def main() -> None:
    cobalt.reset(note=True)
    agent = investigator(middleware=[sees])
    session = agent.create_session()
    result = await agent.run(TASK, session=session, function_invocation_kwargs=run_args())
    print(f"\nThe run returned {len(result.user_input_requests)} approval request(s). "
          f"The analyst {'rejects' if args.reject else 'approves'}.\n")
    result = await agent.run(answer(result.user_input_requests[0], not args.reject), session=session,
                             function_invocation_kwargs=run_args())
    show(result)
    for request in result.user_input_requests:  # ②
        print(f"\nNew approval request: {request.function_call.arguments} ({request.additional_properties.get('reason')})")
    print(f"\n{cobalt.where()}")


asyncio.run(main())
