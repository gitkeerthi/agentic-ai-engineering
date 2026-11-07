"""A lab-only chat client that replies from a script instead of calling a model.

It lets a program test what the framework does with a structured answer, cheaply and the same way every time.
Each reply is text, or a (tool name, arguments, call ID) tuple for one tool request.
"""

import json

from agent_framework import BaseChatClient, ChatMiddlewareLayer, ChatResponse, Content, FunctionInvocationLayer, Message


class ScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    def __init__(self, replies: list, **settings):
        super().__init__(**settings)
        self.replies = list(replies)
        self.sent = []  # each call's messages and options, as the framework passed them

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):
        self.sent.append((list(messages), dict(options)))
        reply = self.replies.pop(0)
        if isinstance(reply, tuple):
            name, arguments, call_id = reply
            call = Content.from_function_call(call_id=call_id, name=name, arguments=json.dumps(arguments))
            return ChatResponse(messages=[Message(role="assistant", contents=[call])], finish_reason="tool_calls")
        return ChatResponse(messages=[Message(role="assistant", contents=[Content.from_text(reply)])], finish_reason="stop")
