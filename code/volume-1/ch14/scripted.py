"""A lab-only chat client that replies from a script instead of calling a model.

It lets a test check what the framework and our code do around an agent step, for free and the same way every
time. Each reply is text, a (tool name, arguments, call ID) tuple for one tool request, or an exception to
raise. Chapter 13's client, with one change: it includes the framework's telemetry layer, as the real client
does, so its calls get `chat` spans with the token counts each scripted reply reports.
"""

import json

from agent_framework import (
    BaseChatClient,
    ChatMiddlewareLayer,
    ChatResponse,
    Content,
    FunctionInvocationLayer,
    Message,
)
from agent_framework.observability import ChatTelemetryLayer


class UnexpectedModelCall(AssertionError):
    """The code under test called the model more often than the script allows."""


class ScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, ChatTelemetryLayer, BaseChatClient):
    OTEL_PROVIDER_NAME = "scripted"

    def __init__(self, replies: list, usage: dict | None = None, **settings):
        super().__init__(**settings)
        self.model = "scripted"
        self.replies = list(replies)
        self.usage = usage or {}  # the token counts every reply reports
        self.sent = []  # each call's messages and options, as the framework passed them

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):
        self.sent.append((list(messages), dict(options)))
        if not self.replies:
            raise UnexpectedModelCall(
                f"model call {len(self.sent)}, but the script has no reply left"
            )
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, tuple):
            name, arguments, call_id = reply
            call = Content.from_function_call(
                call_id=call_id, name=name, arguments=json.dumps(arguments)
            )
            return ChatResponse(
                messages=[Message(role="assistant", contents=[call])],
                finish_reason="tool_calls",
                usage_details=self.usage,
            )
        return ChatResponse(
            messages=[
                Message(role="assistant", contents=[Content.from_text(reply)])
            ],
            finish_reason="stop",
            usage_details=self.usage,
        )
