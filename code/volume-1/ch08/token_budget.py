"""Chapter 8 demo: TokenBudget stops the run before any model call once the run has used its budget."""

import argparse
import asyncio

from investigate import TASK, investigator, show
from middleware import TokenBudget

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--budget", type=int, default=3000)
args = parser.parse_args()

budget = TokenBudget(args.budget)
agent = investigator()
result = asyncio.run(agent.run(TASK, middleware=[budget]))
show(result)
print(f"\nModel calls made: {budget.calls}; tokens used: {budget.used}; budget_spent: {result.additional_properties.get('budget_spent', False)}")
