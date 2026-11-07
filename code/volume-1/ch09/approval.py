"""Chapter 9 demo: the same agent and note, with refile_document marked for approval.

The run ends with an approval request. The program saves the session and the request, so that
decide.py, started later, can answer it. --old-instructions keeps typed_note.py's instructions,
which tell the model not to refile without approval.
"""

import argparse
import asyncio

import cobalt
from investigate import GATED_INSTRUCTIONS, INSTRUCTIONS, TASK, investigator, run_args, save_pending, show

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--old-instructions", action="store_true")
args = parser.parse_args()

cobalt.reset(note=True)
instructions = INSTRUCTIONS if args.old_instructions else GATED_INSTRUCTIONS
agent = investigator(instructions=instructions)  # ①
session = agent.create_session()
result = asyncio.run(agent.run(TASK, session=session,
                               function_invocation_kwargs=run_args()))
show(result)

print(f"\nThe run returned {len(result.user_input_requests)} approval request(s):")
for request in result.user_input_requests:  # ②
    call = request.function_call
    print(f"  {request.id}: {call.name}({call.arguments})")
print(f"\n{cobalt.where()}")

if result.user_input_requests:
    request_id = save_pending(session, result)  # ③
    print(f"Saved the session and the request to state/pending/{request_id}.json")
print(f"Outcome: {'approval requested' if result.user_input_requests else 'no approval requested'}"
      f"{', and REFILED' if cobalt.load()['filings'] else ', nothing refiled'}")
