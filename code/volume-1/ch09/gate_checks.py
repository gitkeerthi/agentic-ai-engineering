"""Chapter 9 demo: the gate's rules and its endings. No model call.

The first block asks the store's rules about three proposed refilings. The second asks the gate who may
answer a queued request: requests here are written straight into the queue, as submit() would. The third
runs the gate end to end with a scripted client in place of the model, through the endings that need care,
including an unclear result that recover() leaves to a person, and an agent that asks again for a call a person
has rejected or that has expired.
The last block checks how the gate keys an approved call: when the model writes a number as a string, when
a run asks for two refilings at once, and when ToolApprovalMiddleware approves a refiling automatically in a
run the gate resumed.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from agent_framework import Agent, ToolApprovalMiddleware

import cobalt
import gate
from scripted import ScriptedClient

logging.getLogger("agent_framework").setLevel(logging.ERROR)

cobalt.reset()
records = cobalt.load()
print("Before review, the store's rules:")
for document_id, case in [("DOC-5531", "RTM-88213"), ("DOC-5531", "RTM-88124"), ("DOC-5599", "RTM-88213")]:
    print(f"  refile {document_id} -> {case}: {cobalt.check_refile(records, document_id, case) or 'allow'}")

now = datetime.now(timezone.utc)
gate._save({
    "REQ-1": {"status": "pending", "requested_by": "lead-044", "expires": (now + timedelta(hours=3)).isoformat()},
    "REQ-2": {"status": "pending", "requested_by": "analyst-207", "expires": (now - timedelta(hours=1)).isoformat()},
    "REQ-3": {"status": "approved", "requested_by": "analyst-207", "expires": (now + timedelta(hours=3)).isoformat()},
})
print("\nWho may answer:")
for request_id, approver in [("REQ-1", "analyst-207"), ("REQ-1", "lead-044"), ("REQ-1", "lead-031"),
                             ("REQ-2", "lead-031"), ("REQ-3", "lead-031")]:
    print(f"  {approver} answers {request_id}: {gate.refusal(request_id, approver) or 'may answer'}")
gate.QUEUE.unlink()

REFILE = ("refile_document", {"document_id": "DOC-5531", "customs_case": "RTM-88213", "expected_version": 1}, "c1")
REFILE_AGAIN = ("refile_document", REFILE[1], "c2")  # the same call, asked for again


async def queued(replies: list, middleware=None, **failures) -> tuple[Agent, str]:
    """Reset, let a scripted agent ask for the refiling, and queue its request. Returns the agent and the request ID."""
    cobalt.reset()
    gate.QUEUE.unlink(missing_ok=True)
    agent = Agent(ScriptedClient(replies, **failures), "Investigate.", tools=[cobalt.refile_document],
                  middleware=middleware)
    session = agent.create_session()
    result = await agent.run("Shipment SH-4471 is three days late. Find out why.", session=session)
    return agent, gate.submit(session, result, requested_by="analyst-207")[0]


def status(request_id: str) -> str:
    entry = gate._load()[request_id]
    return f"{entry['status']}, decision {entry.get('decision')}; {cobalt.where()}"


def statuses() -> list:
    return [(request_id[-6:], entry["status"]) for request_id, entry in gate._load().items()]


async def endings() -> None:
    print("\nEndings, with a scripted client in place of the model:")
    agent, rid = await queued([("refile_document", {"document_id": "DOC-5531", "customs_case": "RTM-88124",
                                                    "expected_version": 1}, "c1"), "done", "done"])
    await gate.close(agent, rid, "refused", gate._load()[rid]["reason"])  # as refiling_gate.py ask does
    sent = agent.client.last_messages
    print(f"  a request the store's rules refuse, closed before review: {status(rid)}")
    print(f"    the model was sent: {' -> '.join(f'{m.role}({m.contents[0].type})' for m in sent)}")
    print(f"    last message: {sent[-1].text}")

    agent, rid = await queued([REFILE, "done"], fail_calls={2})  # the send after the decision fails
    try:
        await gate.decide(agent, rid, "lead-031", approved=False)
    except ConnectionError:
        print(f"  a rejection whose send fails: {status(rid)}")
    agent.client.fail_calls = set()
    agent.client.replies = ["done"]
    await gate.recover(agent, rid)
    print(f"  after recover: {status(rid)}")

    agent, rid = await queued([REFILE, "done"], fail_calls={2})
    try:
        await gate.decide(agent, rid, "lead-031", approved=True)
    except ConnectionError:
        print(f"  an approval whose run fails after the tool ran: {status(rid)}")
    agent.client.fail_calls = set()
    agent.client.replies = ["done"]
    await gate.recover(agent, rid)
    print(f"  after recover: {status(rid)}")

    # A gate that compares the model's raw text: the approved call, sent with "1", runs without its key.
    as_text = ("refile_document", {"document_id": "DOC-5531", "customs_case": "RTM-88213", "expected_version": "1"}, "c1")
    agent, rid = await queued([as_text, "done"])
    validated = gate.validated_arguments
    gate.validated_arguments = lambda request: request.function_call.parse_arguments()
    await gate.decide(agent, rid, "lead-031", approved=True)
    gate.validated_arguments = validated
    print(f"  an approval the store has nothing on, though the tool reports a filing: {status(rid)}")
    try:
        await gate.recover(agent, rid)
    except ValueError as error:
        print(f"  recover refuses: {str(error).replace(rid, rid[-6:])}")

    agent, rid = await queued([REFILE, ("refile_document", {"document_id": "DOC-5531", "customs_case": "RTM-88213",
                                                            "expected_version": 2}, "c2")])
    cobalt.colleague_replaces_invoice()
    await gate.decide(agent, rid, "lead-031", approved=True)
    print(f"  an approval that meets a conflict, and the agent asks again: {status(rid)}")
    print(f"  the queue now: {statuses()}")

    agent, rid = await queued([REFILE, REFILE_AGAIN])
    await gate.decide(agent, rid, "lead-031", approved=False)
    print(f"  a rejection, and the agent asks for the same refiling again: {statuses()}")
    print(f"    reason: {list(gate._load().values())[-1]['reason']}")
    fresh = Agent(ScriptedClient([REFILE]), "Investigate.", tools=[cobalt.refile_document])
    session = fresh.create_session()
    result = await fresh.run("Shipment SH-4471 is three days late. Find out why.", session=session)
    gate.submit(session, result, requested_by="analyst-207")
    print(f"  then a fresh investigation, started on purpose, asks for it: {statuses()}")

    agent, rid = await queued([REFILE, "done", REFILE_AGAIN])
    queue = gate._load()
    queue[rid]["expires"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    gate._save(queue)
    print(f"  pending before the sweep: {list(gate.pending())}")
    await gate.expire_due(agent)
    print(f"  after the sweep: {status(rid)}; the agent asks again: {statuses()}")
    gate.QUEUE.unlink()


async def keys() -> None:
    print("\nKeys:")
    as_text = ("refile_document", {"document_id": "DOC-5531", "customs_case": "RTM-88213", "expected_version": "1"}, "c1")
    agent, rid = await queued([as_text, "done"])
    await gate.decide(agent, rid, "lead-031", approved=True)
    filings = [(f["filing"], f["approved_by"]) for f in cobalt.load()["filings"]]
    print(f"  the model sends expected_version as \"1\": {status(rid)}; filings {filings}; "
          f"under the key: {cobalt.outcome_of(rid) is not None}")
    second = ("refile_document", {"document_id": "DOC-5532", "customs_case": "RTM-88213", "expected_version": 1}, "c2")
    try:
        await queued([[REFILE, second], "done"])
    except ValueError as error:
        print(f"  one reply asks for two refilings: {error}")
    gate.QUEUE.unlink(missing_ok=True)


def certificate_rule(call) -> bool:
    """An automatic approval rule: refiling the certificate of origin needs no person."""
    return call.name == "refile_document" and json.loads(call.arguments)["document_id"] == "DOC-5532"


async def automatic_approval() -> None:
    print("  a refiling approved automatically, in a run the gate resumed:")
    second = ("refile_document", {"document_id": "DOC-5532", "customs_case": "RTM-88213", "expected_version": 1}, "c2")
    agent, rid = await queued([REFILE, second, "done"], middleware=[ToolApprovalMiddleware(auto_approval_rules=[certificate_rule])])
    await gate.decide(agent, rid, "lead-031", approved=True)
    for filing in cobalt.load()["filings"]:
        print(f"    {filing['filing']} {filing['document_id']}, approved by {filing['approved_by']}")
    print(f"    {cobalt.where('DOC-5531')}\n    {cobalt.where('DOC-5532')}")
    gate.QUEUE.unlink()


asyncio.run(endings())
asyncio.run(keys())
asyncio.run(automatic_approval())
