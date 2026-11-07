"""Chapter 2 demo: tool calling on the wire. The model asks for a call; this code runs it and sends the result back."""

import json
import sys

from agentlab.llm import chat

SHIPMENTS = {
    "SH-4471": {"status": "held", "location": "Rotterdam customs", "reason": "commercial invoice not received"},
}


def get_shipment_status(shipment_id: str) -> dict:
    return SHIPMENTS.get(shipment_id, {"error": f"No shipment found with ID {shipment_id}"})


# The model never sees the Python function, only this description of it.
TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_shipment_status",
        "description": "Look up the current status, location and any delay reason for one shipment.",
        "parameters": {
            "type": "object",
            "properties": {"shipment_id": {"type": "string", "description": "Shipment ID, for example SH-4471"}},
            "required": ["shipment_id"],
        },
    },
}]


question = sys.argv[1] if len(sys.argv) > 1 else "Why is shipment SH-4471 late?"
messages = [{"role": "user", "content": question}]

first = chat(messages, tools=TOOLS).choices[0].message
if not first.tool_calls:
    print(f"The model answered without asking for a tool:\n   {first.content}")
    sys.exit()
print("1. The model replies with a request, not an answer:")
print(f"   content    = {first.content!r}")
for call in first.tool_calls:
    print(f"   tool_call  = {call.function.name}({call.function.arguments})")

messages.append(first.model_dump(exclude_none=True))
for call in first.tool_calls:
    result = get_shipment_status(**json.loads(call.function.arguments))
    print(f"\n2. Our code runs the function and gets: {result}")
    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

final = chat(messages, tools=TOOLS).choices[0].message
print(f"\n3. With the result in hand, the model answers:\n   {final.content}")
