"""Chapter 9's refiling gate: the program between the agent's approval requests and the analysts who answer them.

submit() refuses what the store's rules forbid and queues the rest; when the agent asks again after an answer,
it also refuses a call the queue already holds, so a person's no isn't put to anyone again. expire_due() closes
requests whose lifetime has passed. refusal() says who may answer a request and when. decide() records a person's
decision, sends it to the agent, and reads the outcome from the store. recover() settles a decision whose outcome
is unknown. close() answers a request no person will decide.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent_framework import Agent, AgentResponse, AgentSession, Content, Message

import cobalt

QUEUE = Path(__file__).parent / "state" / "queue.json"
APPROVERS = {"lead-031", "lead-044"}  # in production, an identity-provider role
LIFETIME = timedelta(hours=24)
CRASH_BEFORE_SEND = False  # a lab switch: the process dies after recording a decision, before sending it


def _load() -> dict:
    return json.loads(QUEUE.read_text()) if QUEUE.exists() else {}


def _save(queue: dict) -> None:
    QUEUE.parent.mkdir(exist_ok=True)
    QUEUE.write_text(json.dumps(queue, indent=2))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def facts(arguments: dict) -> dict:
    """What the store says now about a proposed refiling, for the reviewer
    to read beside the model's reasoning."""
    records = cobalt.load()
    doc = records["documents"].get(arguments["document_id"], {})
    case = cobalt.CUSTOMS_CASES.get(arguments["customs_case"], {})
    changed = doc.get("version") != arguments["expected_version"]  # ①
    replaced = doc.get("superseded_by")
    return {
        "document": f"{arguments['document_id']}: {doc.get('type')} for "
                    f"{doc.get('shipment_id')}, version {doc.get('version')}",
        "changed since the agent read it": (
            f"yes: version {arguments['expected_version']} then, "
            f"{doc.get('version')} now"
            + (f"; replaced by {replaced}" if replaced else "")
            if changed else "no"),
        "filed against now": doc.get("filed_against_customs_case"),
        "destination": f"{arguments['customs_case']}: case for "
                       f"{case.get('shipment_id')}, {case.get('status')}",
        "store's rules": cobalt.check_refile(records, arguments["document_id"],
                                             arguments["customs_case"])
                         or "allow it",
        "note on the record (typed by the uploader, not checked)":
            doc.get("note", "none"),  # ②
    }


def submit(session: AgentSession, result: AgentResponse, requested_by: str,
           lifetime: timedelta = LIFETIME, asked_again: bool = False) -> list[str]:
    """Queue each approval request the run returned, or refuse it before
    anyone is asked. asked_again: the run that returned it answered an
    earlier one."""
    queue = _load()
    count = len(result.user_input_requests)
    if count > 1:  # one run's runtime values can key only one call
        raise ValueError("the gate takes one request per run; "
                         f"this run returned {count}")
    for request in result.user_input_requests:
        # A run can wait on other things too.
        if request.type != "function_approval_request":
            raise ValueError(
                f"the gate handles approval requests only, not {request.type}")
        arguments = request.function_call.parse_arguments()
        reason = ((asked_again and _repeat_of(request))
                  or cobalt.check_refile(cobalt.load(), arguments["document_id"],
                                         arguments["customs_case"]))  # ①
        queue[request.id] = {
            "status": "refused" if reason else "pending",
            "reason": reason,
            "call": f"{request.function_call.name}"
                    f"({request.function_call.arguments})",
            "model's reasoning": result.messages[-1].text,  # ②
            "requested_by": requested_by,
            "queued": _now().isoformat(timespec="seconds"),
            "expires": (_now() + lifetime).isoformat(timespec="seconds"),
            "request": request.to_dict(),
            "session": session.to_dict(),  # the session as it was before any decision
        }
    _save(queue)
    return list(queue)


def _repeat_of(request: Content) -> str | None:
    """Why a request the agent makes after an answer isn't put to a person:
    the queue already holds the same call. A new version is a new call."""
    call = validated_arguments(request)
    for request_id, entry in _load().items():
        if validated_arguments(Content.from_dict(entry["request"])) == call:
            return f"it repeats {request_id}, which is {entry['status']}"
    return None


def pending() -> dict:
    return {request_id: entry for request_id, entry in _load().items() if entry["status"] == "pending" and not expired(entry)}


async def expire_due(agent: Agent) -> list[str]:
    """Close every pending request whose lifetime has passed.
    In production, a scheduled job runs this."""
    due = [request_id for request_id, entry in _load().items()
           if entry["status"] == "pending" and expired(entry)]
    for request_id in due:
        expires = _load()[request_id]["expires"]
        await close(agent, request_id, "expired",
                    f"the request expired at {expires}")
    return due


def expired(entry: dict) -> bool:
    return _now() > datetime.fromisoformat(entry["expires"])


def refusal(request_id: str, approver: str) -> str | None:
    """Why this person can't answer this request now, or None if they can."""
    entry = _load().get(request_id)
    if entry is None or entry["status"] != "pending":  # ①
        status = entry["status"] if entry else "unknown"
        return f"request {request_id} is not pending ({status})"
    if approver not in APPROVERS:
        return f"{approver} may not approve refilings"
    if approver == entry["requested_by"]:  # ②
        return f"{approver} asked for this refiling and can't also approve it"
    if expired(entry):  # ③
        return f"request {request_id} expired at {entry['expires']}"
    return None


async def decide(agent: Agent, request_id: str, approver: str,
                 approved: bool) -> AgentResponse:
    """Record one person's decision, send it to the agent, and record what
    the store says happened."""
    if reason := refusal(request_id, approver):  # ①
        raise PermissionError(reason)
    decision = "approved" if approved else "rejected"
    _record(request_id, decision=decision, status=decision, decided_by=approver)  # ②
    if CRASH_BEFORE_SEND:
        raise SystemExit("the process died after recording the decision")
    return await _send(agent, request_id)


async def recover(agent: Agent, request_id: str) -> AgentResponse | None:
    """Settle a decision whose outcome is unknown: ask the store, and resend
    the same decision only if nothing was filed."""
    entry = _load()[request_id]
    if entry["status"] == "unclear":  # the session no longer holds the request
        raise ValueError(f"request {request_id} is unclear: a person checks "
                         "the store's filings")
    if entry["status"] not in ("approved", "rejected", "unknown"):
        raise ValueError(f"request {request_id} is {entry['status']}; "
                         "there is nothing to recover")
    if (entry["decision"] == "approved"
            and (stored := cobalt.outcome_of(request_id))):  # ③
        _record(request_id, status="filed", outcome=stored)
        return None
    # The recorded decision, same key: the store files once at most.
    return await _send(agent, request_id)


async def _send(agent: Agent, request_id: str) -> AgentResponse:
    entry = _load()[request_id]
    # The person's decision, never the request's status.
    approved = entry["decision"] == "approved"
    request = Content.from_dict(entry["request"])
    session = AgentSession.from_dict(entry["session"])
    values = {"user_id": entry["requested_by"]}
    if approved:  # ④ the values the tool keys on, sent with an approval only
        values |= {"approved_by": entry["decided_by"], "approval_id": request_id,
                   "approved_arguments": validated_arguments(request)}
    try:
        response = request.to_function_approval_response(approved)
        result = await agent.run(Message(role="user", contents=[response]),
                                 session=session, function_invocation_kwargs=values)
    except Exception:
        _record(request_id, status="unknown")  # ⑤
        raise
    if not approved:
        _record(request_id, status="rejected", outcome="nothing filed",
                session=session.to_dict())
    else:
        stored = cobalt.outcome_of(request_id)  # ⑥
        answer = _tool_answer(result)
        # Nothing under the key, but the tool reports a filing: the record
        # can't tell, so don't say "not filed". A person checks, not recover().
        status = ("filed" if stored
                  else "unclear" if _reports_filing(answer) else "not filed")
        _record(request_id, status=status, outcome=stored or answer,
                session=session.to_dict())
    # The agent asked again: a new call goes to review, a repeat is refused.
    if result.user_input_requests:  # ⑦
        submit(session, result, entry["requested_by"], asked_again=True)
    return result


def _reports_filing(answer) -> bool:
    """Whether the tool's answer says a filing was made."""
    try:
        answer = json.loads(answer) if isinstance(answer, str) else answer
    except ValueError:
        return False
    return isinstance(answer, dict) and "filing" in answer


def validated_arguments(request: Content) -> dict:
    """The approved call's arguments as the tool receives them: checked against its schema, as the framework does."""
    return cobalt.refile_document.input_model.model_validate(request.function_call.parse_arguments()).model_dump()


def _tool_answer(result: AgentResponse):
    """What the refiling tool returned to the model in this run, if it ran."""
    for message in result.messages:
        for content in message.contents:
            if content.type == "function_result":
                return content.result
    return None


def _record(request_id: str, **fields) -> None:
    queue = _load()
    queue[request_id].update(fields)
    _save(queue)


async def close(agent: Agent, request_id: str, status: str, reason: str) -> AgentResponse:
    """Answer a request no person will decide (refused before review, or expired), so the agent learns why
    and the session has no open request."""
    _record(request_id, status=status, reason=reason)
    entry = _load()[request_id]
    request = Content.from_dict(entry["request"])
    session = AgentSession.from_dict(entry["session"])
    values = {"user_id": entry["requested_by"]}
    await agent.run(Message(role="user", contents=[request.to_function_approval_response(False)]),
                    session=session, function_invocation_kwargs=values)
    # The framework's rejection carries no reason, and text sent with a decision would land between the model's
    # tool call and its result, which the provider rejects. So the reason goes in a run of its own.
    result = await agent.run(f"Your refiling request was not approved ({status}): {reason}.",
                             session=session, function_invocation_kwargs=values)
    _record(request_id, session=session.to_dict())
    if result.user_input_requests:  # the agent asked again: a new call goes to review, a repeat is refused
        submit(session, result, entry["requested_by"], asked_again=True)
    return result
