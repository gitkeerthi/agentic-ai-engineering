"""A lab-only chat client that replies from a script instead of calling a model.

It lets a program test what the framework stores, cheaply and the same way every time.
Each reply is text, or a (tool name, arguments, call ID) tuple for one tool request.
"""

import json

from agent_framework import BaseChatClient, ChatMiddlewareLayer, ChatResponse, Content, FunctionInvocationLayer, Message


class ScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    def __init__(self, replies: list, fail_call: int | None = None, **settings):
        super().__init__(**settings)
        self.replies = list(replies)
        self.fail_call = fail_call  # raise on this model call (1 is the first), as a dropped connection would
        self.calls = 0

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):
        self.calls += 1
        if self.calls == self.fail_call:
            raise ConnectionError(f"model call {self.calls} failed")
        reply = self.replies.pop(0)
        if isinstance(reply, tuple):
            name, arguments, call_id = reply
            call = Content.from_function_call(call_id=call_id, name=name, arguments=json.dumps(arguments))
            return ChatResponse(messages=[Message(role="assistant", contents=[call])], finish_reason="tool_calls")
        return ChatResponse(messages=[Message(role="assistant", contents=[Content.from_text(reply)])], finish_reason="stop")
