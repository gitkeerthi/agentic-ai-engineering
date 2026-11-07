"""A lab-only chat client that replies from a script instead of calling a model.

It lets a test check what the framework and our code do around an agent step, for free and the same way every
time. Each reply is text, a (tool name, arguments, call ID) tuple for one tool request, or an exception to
raise. Chapter 11's client, with one change: a call after the script runs out fails with a message that says
so, instead of an IndexError from deep inside the framework.
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


class UnexpectedModelCall(AssertionError):
    """The code under test called the model more often than the script allows."""


class ScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    def __init__(self, replies: list, **settings):
        super().__init__(**settings)
        self.replies = list(replies)
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
            )
        return ChatResponse(
            messages=[
                Message(role="assistant", contents=[Content.from_text(reply)])
            ],
            finish_reason="stop",
        )
