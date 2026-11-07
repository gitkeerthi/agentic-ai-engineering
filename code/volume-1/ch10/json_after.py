"""Chapter 10 demo: keep the notes and still use JSON mode, by asking for the finding in a run of its own.

The investigation runs with JSON_INSTRUCTIONS and no response format, so the notes before each tool call
survive. A second run on the same session, with tools off and JSON mode on, asks for the finding.
"""

import asyncio
import sys

from contracts import check
from investigate import JSON_INSTRUCTIONS, TASK, investigator

FINISH = "Reply with your finding as the one JSON object your instructions describe."


async def main(task: str) -> None:
    agent = investigator(instructions=JSON_INSTRUCTIONS)
    session = agent.create_session()
    result = await agent.run(task, session=session)  # ①
    notes = [m.text for m in result.messages[:-1] if m.role == "assistant" and m.text]
    print(f"Notes before tool calls: {len(notes)}, of which blank: {sum(not n.strip() for n in notes)}")

    final = await agent.run(FINISH, session=session, options={  # ②
        "tool_choice": "none", "response_format": {"type": "json_object"}})
    reply = final.messages[-1].text
    finding, verdict = check(reply)
    print(f"Reply:\n{reply}\n\nCheck: {verdict}")
    print(f"Outcome: {verdict}{'; status ' + finding.status if finding else ''}")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else TASK))
