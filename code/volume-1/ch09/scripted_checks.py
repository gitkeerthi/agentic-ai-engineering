"""Chapter 9 demo: what the framework does around an approval, tested with a scripted client. No model call.

Six checks, each with a tool that needs approval (refile) and one that doesn't (lookup):
1. one reply asks for both tools, with and without a session
2. without a session, a response sent back as approved, and one altered on its way back
3. what the model is sent when text goes with a decision
4. the loop's iteration and call limits across the round-trip, with and without ToolApprovalMiddleware
5. the session after a resumed run fails
6. one reply asks for two refilings, and the decisions come back one at a time
"""

import asyncio
import json
import logging

from agent_framework import Agent, Content, Message, ToolApprovalMiddleware, tool

from scripted import ScriptedClient

logging.getLogger("agent_framework").setLevel(logging.ERROR)
ran = []


@tool(approval_mode="always_require")
def refile(document_id: str) -> str:
    """Refile a document."""
    ran.append(f"refile {document_id}")
    return "filed"


@tool
def lookup(record_id: str) -> str:
    """Look up a record."""
    ran.append(f"lookup {record_id}")
    return "found"


REFILE = ("refile", {"document_id": "DOC-5531"}, "call-1")


def agent(replies: list, middleware=None, **limits) -> Agent:
    client = ScriptedClient(replies, fail_without_tools=limits.pop("fail_without_tools", False))
    client.function_invocation_configuration.update(limits)
    return Agent(client, "Investigate.", tools=[refile, lookup], middleware=middleware)


def approve(request) -> Message:
    return Message(role="user", contents=[request.to_function_approval_response(True)])


async def both_in_one_reply() -> None:
    print("1. One reply asks for refile and lookup")
    for with_session in (True, False):
        ran.clear()
        a = agent([[("lookup", {"record_id": "SH-4471"}, "call-0"), REFILE], "done", "done"])
        session = a.create_session() if with_session else None
        result = await a.run("go", session=session)
        asked = [r.function_call.name for r in result.user_input_requests]
        print(f"   {'with' if with_session else 'without'} a session: approval asked for {asked}; ran before the decision: {ran}")
        if with_session:
            await a.run(approve(result.user_input_requests[0]), session=session)
            print(f"   after approving refile: ran {ran}")


async def altered_without_session() -> None:
    print("2. A response sent back without a session, as approved and altered on its way back")
    for altered in (False, True):
        ran.clear()
        a = agent([REFILE, "done", "done"])
        result = await a.run("go")
        request = result.user_input_requests[0]
        decision = Content.from_dict(request.to_function_approval_response(True).to_dict())
        if altered:
            decision.function_call.arguments = '{"document_id": "DOC-5532"}'
        history = [Message(role="user", contents=["go"]), Message(role="assistant", contents=[request]),
                   Message(role="user", contents=[decision])]
        await a.run(history)
        sent = "DOC-5532" if altered else "DOC-5531"
        print(f"   approved DOC-5531, sent back {sent}: ran {ran}")


async def text_with_a_decision() -> None:
    print("3. What the model is sent on resume")
    for label, extra in (("decision alone", []), ("decision, then a text message", ["Approved by lead-031."])):
        a = agent([REFILE, "done"])
        session = a.create_session()
        request = (await a.run("go", session=session)).user_input_requests[0]
        messages = [approve(request)] + [Message(role="user", contents=[text]) for text in extra]
        await a.run(messages, session=session)
        sent, _ = a.client.sent[-1]
        print(f"   {label}: {' -> '.join(f'{role}({types[0]})' for role, types in sent)}")


async def limits_across_the_round_trip() -> None:
    print("4. Limits across the round-trip (one lookup before the request, one after)")
    script = [("lookup", {"record_id": "SH-4471"}, "c0"), REFILE, ("lookup", {"record_id": "RTM-88213"}, "c2"), "done", "done"]
    for harness in (False, True):
        for limit in ({"max_iterations": 3}, {"max_function_calls": 2}):
            ran.clear()
            a = agent(list(script), middleware=[ToolApprovalMiddleware()] if harness else None, **limit)
            session = a.create_session()
            request = (await a.run("go", session=session)).user_input_requests[0]
            await a.run(approve(request), session=session)
            tools_off = [i + 1 for i, (_, choice) in enumerate(a.client.sent) if choice == "none"]
            print(f"   {'ToolApprovalMiddleware' if harness else 'plain Agent':<22} {limit}: ran {ran}; "
                  f"tools-off call: {('model call ' + str(tools_off[0])) if tools_off else 'none'}")


async def session_after_a_failed_resume() -> None:
    print("5. ToolApprovalMiddleware, a 1-second time limit, an approval after 2 seconds")
    ran.clear()
    a = agent([REFILE, "done"], middleware=[ToolApprovalMiddleware()], max_duration_seconds=1, fail_without_tools=True)
    session = a.create_session()
    request = (await a.run("go", session=session)).user_input_requests[0]
    await asyncio.sleep(2)
    for attempt in (1, 2):
        try:
            await a.run(approve(request), session=session)
        except Exception as error:
            pending = session.state.get("tool_approval", {}).get("pending_approval_requests", [])
            print(f"   attempt {attempt}: raised ({error.__cause__ or error}); ran {ran}; pending requests left: {len(pending)}")


async def two_requests_from_one_reply() -> None:
    print("6. One reply asks for two refilings; the decisions come back one at a time")
    ran.clear()
    a = agent([[REFILE, ("refile", {"document_id": "DOC-5532"}, "call-2")], "done"])
    session = a.create_session()
    first, second = (await a.run("go", session=session)).user_input_requests
    for name, request in (("first", first), ("second", second)):
        result = await a.run(approve(request), session=session)
        still = [json.loads(r.function_call.arguments)["document_id"] for r in result.user_input_requests]
        print(f"   after the {name} decision: ran {ran}; still waiting for {still}; model calls so far: {len(a.client.sent)}")


async def main() -> None:
    for check in (both_in_one_reply, altered_without_session, text_with_a_decision,
                  limits_across_the_round_trip, session_after_a_failed_resume, two_requests_from_one_reply):
        await check()


asyncio.run(main())
