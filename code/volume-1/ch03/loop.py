"""The agent loop written out by hand, with no framework, so every part of the agent is visible."""

import json

from agentlab.llm import chat
from cobalt import TOOL_DESCRIPTIONS, TOOLS


def execute(name: str, arguments: str) -> dict:
    """The control point: the application, not the model, decides whether and how a request runs."""
    if name not in TOOLS:
        return {"error": f"Unknown tool {name}"}
    try:
        return TOOLS[name](**json.loads(arguments))
    except (json.JSONDecodeError, TypeError) as exc:
        # Sent back as a result so the model can correct its request.
        return {"error": f"Bad arguments for {name}: {exc}"}


def run_agent(instructions: str, task: str, max_steps: int = 10, trace: bool = True) -> dict:
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": task},
    ]
    total_tokens = 0
    for step in range(1, max_steps + 1):
        response = chat(messages, tools=TOOL_DESCRIPTIONS)
        reply = response.choices[0].message
        total_tokens += response.usage.total_tokens
        messages.append(reply.model_dump(exclude_none=True))
        if trace:
            print(f"\n--- Turn {step}: the model read {len(messages) - 1} messages ({response.usage.prompt_tokens} tokens)")
            if reply.content:
                print(f"Model says: {reply.content.strip()}")

        if not reply.tool_calls:
            return {"answer": reply.content, "turns": step, "tokens": total_tokens, "messages": messages}

        for call in reply.tool_calls:
            result = execute(call.function.name, call.function.arguments)
            if trace:
                print(f"Model asks: {call.function.name}({call.function.arguments})")
                print(f"Result:     {json.dumps(result)}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    return {"answer": None, "turns": max_steps, "tokens": total_tokens, "messages": messages}
