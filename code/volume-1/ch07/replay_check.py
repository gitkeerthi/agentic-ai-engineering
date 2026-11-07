"""Chapter 7 check: what the framework's history providers store when messages repeat. A scripted client
replies instead of a model, so no model is called and every run gives the same output.

1. The same question in runs 1 and 3 of one session.
2. The same question twice in a row, with the same reply, then with a different one.
3. A run that fails partway, saved after every model call, then resumed with the same task.
4. A store-only audit copy over three runs: as configured in several_providers.py, without
   store_context_from, and with store_context_from but without store_context_messages.

    uv run python ch07/replay_check.py
"""

import asyncio
import tempfile
from pathlib import Path

from agent_framework import Agent, AgentSession, FileHistoryProvider, InMemoryHistoryProvider

from cobalt import TOOLS, pick_up_sh4471, release_sh4471, reset
from investigate import CUSTOMER_UPDATE, FIRST_TASK
from providers import Findings, RepairingFileHistory, ShipmentStatus
from scripted import ScriptedClient

NETHERLANDS = "Name a port in the Netherlands."
BELGIUM = "Name one in Belgium."
ANSWER = "Cause: The invoice was filed against the wrong case.\nEvidence: SH-4471, RTM-88213\nRecommended action: Refile it."


async def stored_after(exchanges: list[tuple[str, str]]) -> None:
    agent = Agent(ScriptedClient([reply for _, reply in exchanges]), "Answer in five words or fewer.")
    session = agent.create_session()
    for question, _ in exchanges:
        await agent.run(question, session=session)
    for n, (question, reply) in enumerate(exchanges, start=1):
        print(f"  Run {n}: {question} -> {reply}")
    print("  Stored:")
    for message in session.state["in_memory"]["messages"]:
        print(f"    {message.role:<9} {message.text!r}")


async def resume(folder: Path) -> None:
    session_id = "replay-check"
    failing = Agent(
        ScriptedClient([("get_shipment_status", {"shipment_id": "SH-4471"}, "call-1"),
                        ("get_customs_case", {"case_id": "RTM-88213"}, "call-2")], fail_call=3),
        "Investigate.", tools=TOOLS, context_providers=[RepairingFileHistory(folder)],
        require_per_service_call_history_persistence=True,
    )
    try:
        await failing.run(FIRST_TASK, session=AgentSession(session_id=session_id))
    except ConnectionError as error:
        print(f"  The first attempt failed: {error}")
    resumed = Agent(
        ScriptedClient([("list_required_documents", {"case_id": "RTM-88213"}, "call-3"), ANSWER]),
        "Investigate.", tools=TOOLS, context_providers=[RepairingFileHistory(folder)],
    )
    await resumed.run(FIRST_TASK, session=AgentSession(session_id=session_id))
    print("  The second attempt finished. The file holds:")
    for message in await FileHistoryProvider(folder).get_messages(session_id):
        detail = repr(message.text) if message.role == "user" else ", ".join(c.type for c in message.contents)
        print(f"    {message.role:<9} {detail}")


async def audit_copy(label: str, **settings) -> None:
    reset()
    audit = InMemoryHistoryProvider("audit", load_messages=False, **settings)
    providers = [InMemoryHistoryProvider(), audit, Findings(), ShipmentStatus()]
    replies = [("get_shipment_status", {"shipment_id": "SH-4471"}, "call-1"), ANSWER,
               "Your shipment has been released.", "It is on a truck to Duisburg."]
    agent = Agent(ScriptedClient(replies), "Investigate.", tools=TOOLS, context_providers=providers)
    session = agent.create_session()
    counts = []
    for change, question in [(None, FIRST_TASK), (release_sh4471, CUSTOMER_UPDATE), (pick_up_sh4471, "Where is it now?")]:
        if change:
            change()
        await agent.run(question, session=session)
        stored = session.state["audit"].get("messages", [])
        notes = sum(m.text.startswith(("Current shipment records", "Findings from")) for m in stored)
        counts.append(f"{len(session.state['in_memory']['messages'])} / {len(stored)} ({notes})")
    print(f"    {label:<48}{', '.join(counts)}")


async def main() -> None:
    print("1. The same question in runs 1 and 3")
    await stored_after([(NETHERLANDS, "Rotterdam"), (BELGIUM, "Antwerp"), (NETHERLANDS, "Rotterdam")])
    print("\n2. The same question twice in a row, with the same reply, then with a different one")
    await stored_after([(NETHERLANDS, "Rotterdam"), (NETHERLANDS, "Rotterdam")])
    await stored_after([(NETHERLANDS, "Rotterdam"), (NETHERLANDS, "Amsterdam")])
    print("\n3. A failed run, saved after every model call, resumed with the same task")
    with tempfile.TemporaryDirectory() as folder:
        await resume(Path(folder))
    print("\n4. A store-only audit copy over three runs")
    print("  Working history / audit copy after runs 1, 2 and 3 (notes in the audit copy):")
    notes = {"shipment_status", "findings"}
    await audit_copy("store_context_messages and store_context_from:",
                     store_context_messages=True, store_context_from=notes)
    await audit_copy("store_context_messages only:", store_context_messages=True)
    await audit_copy("store_context_from only:", store_context_from=notes)


asyncio.run(main())
