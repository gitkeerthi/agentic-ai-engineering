"""Chapter 9 demo: an approval given after the record changed.

The agent asks to refile DOC-5531. While the request waits, a colleague uploads a corrected invoice,
DOC-5540, files it against RTM-88213, and marks DOC-5531 as replaced. Then the analyst approves.
--no-version-check makes the store ignore the version the agent read.
"""

import argparse
import asyncio

import cobalt
from investigate import TASK, answer, investigator, run_args, show

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--no-version-check", action="store_true")
args = parser.parse_args()
cobalt.COMPARE_VERSIONS = not args.no_version_check


async def main() -> None:
    cobalt.reset(note=True)
    agent = investigator()
    session = agent.create_session()
    result = await agent.run(TASK, session=session, function_invocation_kwargs=run_args())
    request = result.user_input_requests[0]
    print(f"Requested: {request.function_call.name}({request.function_call.arguments})\n")

    cobalt.colleague_replaces_invoice()  # ①
    print(f"Meanwhile: {cobalt.where('DOC-5540')}")
    print(f"           {cobalt.where('DOC-5531')}\n")

    print("The analyst approves the request.\n")
    show(await agent.run(answer(request, True), session=session, function_invocation_kwargs=run_args()))
    records = cobalt.load()
    print(f"\n{cobalt.where('DOC-5531')}")
    print("Commercial invoices filed against RTM-88213: "
          f"{[f['document_id'] for f in records['filings'] if f['customs_case'] == 'RTM-88213']}")


asyncio.run(main())
