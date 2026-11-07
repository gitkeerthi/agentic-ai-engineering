"""A lab-only chat client that replies from a script instead of calling a model.

It lets a program test what the framework does around approvals, cheaply and the same way every time.
Each reply is text, a (tool name, arguments, call ID) tuple for one tool request, or a list of such tuples
for several tool requests in one reply.
"""

import json

from agent_framework import BaseChatClient, ChatMiddlewareLayer, ChatResponse, Content, FunctionInvocationLayer, Message


class ScriptedClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    def __init__(self, replies: list, fail_without_tools: bool = False, fail_calls: tuple = (), **settings):
        super().__init__(**settings)
        self.replies = list(replies)
        self.fail_without_tools = fail_without_tools  # raise on a tools-off call, as the provider's 400 does
        self.fail_calls = set(fail_calls)  # raise on these model calls (1 is the first), as a dropped connection would
        self.sent = []  # what each call was sent: (role, content types) per message, and tool_choice
        self.last_messages = []  # the messages the latest call was sent

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):
        self.sent.append(([(m.role, [c.type for c in m.contents]) for m in messages], options.get("tool_choice")))
        self.last_messages = list(messages)
        if len(self.sent) in self.fail_calls:
            raise ConnectionError(f"model call {len(self.sent)} failed")
        if self.fail_without_tools and options.get("tool_choice") == "none":
            raise RuntimeError("400: an assistant message with 'tool_calls' must be followed by tool messages")
        reply = self.replies.pop(0)
        if isinstance(reply, (tuple, list)):
            calls = [Content.from_function_call(call_id=call_id, name=name, arguments=json.dumps(arguments))
                     for name, arguments, call_id in (reply if isinstance(reply, list) else [reply])]
            return ChatResponse(messages=[Message(role="assistant", contents=calls)], finish_reason="tool_calls")
        return ChatResponse(messages=[Message(role="assistant", contents=[Content.from_text(reply)])], finish_reason="stop")
