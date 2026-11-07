"""Chapter 8 demo: the investigation agent with the chapter's interception plan, all together.

On the agent: the audit trail and the limit report. For each run: a token budget and a repeat stop.
--budget, --max-iterations, --store-busy and --store-down make the controls fire.
"""

import argparse
import asyncio

import audit_store
import cobalt
from cobalt import TOOLS, get_customer_contact
from investigate import WITH_UPDATE, investigator, outcome, run_args, show
from middleware import RepeatStop, TokenBudget, audit_trail, limit_report

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--budget", type=int, default=20000)
parser.add_argument("--max-iterations", type=int, default=9)
parser.add_argument("--store-busy", action="store_true")
parser.add_argument("--store-down", action="store_true")
args = parser.parse_args()

agent = investigator(
    tools=[*TOOLS, get_customer_contact],
    max_iterations=args.max_iterations,
    middleware=[audit_trail, limit_report],  # ①
)
audit_store.clear()
if args.store_busy:
    cobalt.make_store_busy()
audit_store.state["down"] = args.store_down
try:
    per_run = [TokenBudget(args.budget), RepeatStop()]  # ②
    result = asyncio.run(agent.run(WITH_UPDATE, middleware=per_run,
                                   function_invocation_kwargs=run_args()))
    show(result)
    print(f"\nOutcome: {outcome(result)}")
except Exception as error:  # ③
    print(f"Outcome: run raised {type(error).__name__}: {error}")
print()
audit_store.show()
