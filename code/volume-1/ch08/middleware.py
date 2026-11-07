"""The chapter's middleware: an audit trail, a report at any loop limit, a repeat stop and a token budget,
and the token budget again as an Agent Hooks interceptor."""

import json
import logging
from datetime import datetime, timezone

from agent_framework import (
    ChatContext,
    ChatMiddleware,
    ChatResponse,
    Content,
    FunctionInvocationContext,
    FunctionMiddleware,
    Message,
    MiddlewareFailure,
    MiddlewareTermination,
    chat_middleware,
    function_middleware,
)

from agent_hooks import Verdict

import audit_store

PERSONAL_FIELDS = {"contact_name", "email", "phone"}
alerts = logging.getLogger("audit")


def redact(value: object) -> object:
    """A copy with the values of personal fields replaced, at any depth."""
    if isinstance(value, dict):
        return {
            k: "[redacted]" if k in PERSONAL_FIELDS else redact(v)  # ①
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]  # ②
    return value


def result_data(result: list[Content]) -> object:
    """The tool's result as data: the framework hands middleware a list of Content items."""
    text = "".join(c.text or "" for c in result)
    try:
        return json.loads(text)
    except ValueError:
        return text


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def finish(record: dict, **outcome) -> None:
    """Write how a call ended. The call has happened, so any failure here
    raises an alert, never an error."""
    try:
        if "result" in outcome:  # prepared inside the guard, like the write
            outcome["result"] = redact(result_data(outcome["result"]))
        audit_store.write({**record, "time": now(), **outcome})
    except Exception as error:
        alerts.error("Audit record of a %s %s call not written: %s",
                     outcome["phase"], record["tool"], error)


@function_middleware
async def audit_trail(context: FunctionInvocationContext, call_next) -> None:
    """Record every tool call: who it was for, which tool, which arguments,
    and how it ended."""
    user = context.kwargs.get("user_id")
    if not user:
        raise MiddlewareFailure(  # ①
            "No user identity for this run; tool calls are not allowed without one.")
    record = {
        "time": now(),
        "user": user,
        "run": context.kwargs.get("run_id"),
        "call": context.metadata.get("call_id"),
        "tool": context.function.name,
        "arguments": redact(dict(context.arguments)),
    }
    try:
        audit_store.write({**record, "phase": "requested"})  # ②
    except Exception as error:
        raise MiddlewareFailure(
            f"Audit store unavailable; {record['tool']} was not run.") from error
    try:
        await call_next()
    except BaseException as error:  # ③
        if isinstance(error, MiddlewareTermination):
            finish(record, phase="stopped", reason=str(error))
        else:
            finish(record, phase="failed", error=type(error).__name__)
        raise
    finish(record, phase="completed", result=context.result)  # ④


REPORT_REQUEST = (
    "You have used every lookup this run allows. Don't request any more tools. "
    "Report what you have found so far in the answer format, "
    "and say what is still unknown."
)


@chat_middleware
async def limit_report(context: ChatContext, call_next) -> None:
    """On the call the framework makes with tools switched off at a loop limit,
    ask for a report and flag it."""
    at_limit = context.options.get("tool_choice") == "none"  # ①
    if not at_limit:
        await call_next()
        return
    context.messages = [*context.messages, Message("user", [REPORT_REQUEST])]  # ②
    try:
        await call_next()
    finally:
        if context.result is not None:
            context.result.additional_properties["limit_reached"] = True  # ③


class RepeatStop(FunctionMiddleware):
    """End the run when the model makes the same tool request a third time.
    Register one per run."""

    def __init__(self, allowed: int = 2) -> None:
        self.allowed = allowed
        self.seen: dict[str, int] = {}

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        arguments = json.dumps(dict(context.arguments), sort_keys=True)
        key = f"{context.function.name}({arguments})"  # ①
        self.seen[key] = self.seen.get(key, 0) + 1
        if self.seen[key] > self.allowed:
            reason = f"Stopped: {key} requested {self.seen[key]} times."
            raise MiddlewareTermination(reason, result=reason)  # ②
        await call_next()


class TokenBudget(ChatMiddleware):
    """Stop before any model call once the run has used its token budget.
    Register one per run."""

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self.used = 0
        self.calls = 0

    async def process(self, context: ChatContext, call_next) -> None:
        if self.used >= self.budget:  # ①
            context.result = ChatResponse(
                messages=[Message("assistant", [
                    f"Stopped: token budget of {self.budget} spent "
                    f"after {self.calls} model calls."])],
                additional_properties={"budget_spent": True},
            )
            raise MiddlewareTermination("token budget spent")
        await call_next()
        usage = context.result.usage_details or {}
        self.used += (usage.get("input_token_count", 0)  # ②
                      + usage.get("output_token_count", 0))
        self.calls += 1


class BudgetGuard:
    """Agent Hooks interceptor: deny the next model call once the run
    has used its token budget."""

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self.used: dict[str, int] = {}  # tokens used, by hooks session (one per run)

    def intercept(self, context) -> Verdict:
        point = context["interception_point"]
        run = context["session"]["id"]  # ①
        if point == "post_model_call":  # ②
            usage = context.get("usage") or {}
            tokens = (usage.get("input_token_count", 0)
                      + usage.get("output_token_count", 0))
            self.used[run] = self.used.get(run, 0) + tokens
        spent = self.used.get(run, 0) >= self.budget
        if point == "pre_model_call" and spent:  # ③
            return Verdict.deny(
                reason=f"token budget of {self.budget} spent "
                       f"({self.used[run]} used)")
        if point == "agent_shutdown":
            self.used.pop(run, None)
        return Verdict.allow()
