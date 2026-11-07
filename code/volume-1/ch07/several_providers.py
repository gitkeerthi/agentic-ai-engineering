"""Chapter 7 demo: four context providers on one agent. A file-backed history that loads and saves the
conversation; a store-only copy for audit that also keeps what the other providers added; the findings of
earlier investigations; and the current shipment records, last, just before the question. The records change twice during the conversation.

    uv run python ch07/several_providers.py
"""

import asyncio
from pathlib import Path

from agent_framework import AgentSession, ChatContext, FileHistoryProvider, chat_middleware

from cobalt import pick_up_sh4471, release_sh4471
from investigate import CUSTOMER_UPDATE, FIRST_TASK, investigator, show
from providers import Findings, RepairingFileHistory, ShipmentStatus

FOLDER = Path(__file__).parent / "history"
SESSION_ID = "several-providers"
LAST_QUESTION = "Where is SH-4471 now, and what had held it up?"

providers = [
    RepairingFileHistory(FOLDER),
    FileHistoryProvider(
        FOLDER / "audit", source_id="audit", load_messages=False,
        store_context_messages=True,
        store_context_from={"shipment_status", "findings"},
    ),
    Findings(),
    ShipmentStatus(),
]
sent: list[str] = []  # where each message of the latest model call came from


@chat_middleware
async def record_sources(context: ChatContext, call_next) -> None:
    sent[:] = [m.additional_properties.get("_attribution", {}).get("source_id", "the caller") for m in context.messages]
    await call_next()


async def main() -> None:
    for path in [FOLDER / f"{SESSION_ID}.jsonl", FOLDER / "audit" / f"{SESSION_ID}.jsonl"]:
        path.unlink(missing_ok=True)
    agent = investigator(context_providers=providers)
    agent.middleware.append(record_sources)
    session = AgentSession(session_id=SESSION_ID)

    for change, question in [(None, FIRST_TASK), (release_sh4471, CUSTOMER_UPDATE), (pick_up_sh4471, LAST_QUESTION)]:
        if change:
            change()
        result = await agent.run(question, session=session)
    print(f"Question: {LAST_QUESTION}\n")
    show(result)

    print("\nThe last model call's messages, by where they came from:")
    print("  " + ", ".join(f"{source} x{sent.count(source)}" for source in dict.fromkeys(sent)))
    history = await FileHistoryProvider(FOLDER).get_messages(SESSION_ID)
    audit = await FileHistoryProvider(FOLDER / "audit").get_messages(SESSION_ID)
    notes = sum(m.text.startswith(("Current shipment records", "Findings from")) for m in audit)
    print(f"History file: {len(history)} messages. Audit file: {len(audit)} messages, of which provider notes: {notes}")
    print(f"Provider state in the session: {session.state}")


asyncio.run(main())
