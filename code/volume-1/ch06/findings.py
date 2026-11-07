"""Chapter 6 demo: the program keeps each investigation's findings in the session, outside the history, and sends
them with every run as extra instructions. The last question is asked with the same sliding window as
`compaction.py --strategy sliding-window`.

    uv run python ch06/findings.py
"""

import asyncio
import re

from agent_framework import AgentSession, CharacterEstimatorTokenizer, SlidingWindowStrategy

from investigate import FIRST_TASK, FOLLOW_UP, GO_BACK, SECOND_TASK, investigator, show

IDS = r"\b(?:SH|RTM|DOC)-\d+\b"


def line(label: str, answer: str) -> str:
    match = re.search(rf"^\W*(?:\w+ )?{label}[^:]*:\W*(.+)$", answer, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip(" *") if match else "(not stated)"


def record_findings(session: AgentSession, task: str, answer: str) -> None:
    """After an investigation, keep what the team will act on: the shipment, the cause, the action and the IDs.
    Read from the answer's fixed format; Chapter 10's structured output makes this reliable."""
    shipment = re.search(r"SH-\d{4}", task)
    if not shipment or "Cause" not in answer:
        return
    session.state.setdefault("findings", []).append({
        "shipment": shipment.group(),
        "cause": line("Cause", answer),
        "action": line("Recommended action", answer),
        "ids": sorted(set(re.findall(IDS, answer))),
    })


def findings_note(session: AgentSession) -> str | None:
    findings = session.state.get("findings")
    if not findings:
        return None
    entries = [
        f"{n}. {f['shipment']}. Cause: {f['cause']} Action: {f['action']} IDs: {', '.join(f['ids'])}"
        for n, f in enumerate(findings, start=1)
    ]
    return "Findings from earlier investigations in this conversation, oldest first:\n" + "\n".join(entries)


async def main() -> None:
    agent = investigator()
    session = agent.create_session()
    window = SlidingWindowStrategy(keep_last_groups=5)
    for question in [FIRST_TASK, FOLLOW_UP, SECOND_TASK, GO_BACK]:
        note = findings_note(session)
        settings = {"compaction_strategy": window, "tokenizer": CharacterEstimatorTokenizer()} if question == GO_BACK else {}
        result = await agent.run(
            question, session=session, options={"instructions": note}, **settings
        )
        record_findings(session, question, result.messages[-1].text)

    print(f"Sent with the last question, as instructions:\n{note}\n")
    print(f"Question: {GO_BACK}  (compaction: sliding-window)\n")
    show(result)


asyncio.run(main())
