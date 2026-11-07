"""Chapter 10 demo: one repair attempt when a reply fails the check.

The investigation asks for the JSON in the instructions only (no JSON mode), as on a provider without one.
If the reply fails the check, the program sends the failure back once, on the same session, with tools off,
and checks the second reply the same way.
"""

import asyncio
import sys

from contracts import check
from investigate import JSON_INSTRUCTIONS, TASK, investigator

REPAIR = """Your last reply failed the program's check: {verdict}.
Reply again with only the JSON object, matching the schema in your instructions.
Fix what the check names, and change nothing else about your finding."""  # ①


async def main(task: str) -> None:
    agent = investigator(instructions=JSON_INSTRUCTIONS)
    session = agent.create_session()
    result = await agent.run(task, session=session)
    reply = result.messages[-1].text
    finding, verdict = check(reply)
    print(f"First reply:\n{reply}\n\nCheck: {verdict}")
    if finding:
        print(f"Outcome: valid first time; status {finding.status}")
        return

    repaired = await agent.run(REPAIR.format(verdict=verdict), session=session,
                               options={"tool_choice": "none"})  # ②
    second = repaired.messages[-1].text
    finding, verdict = check(second)  # ③
    print(f"\nRepaired reply:\n{second}\n\nCheck: {verdict}")
    print(f"Outcome: {'repaired; status ' + finding.status if finding else 'still invalid: ' + verdict}")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else TASK))
