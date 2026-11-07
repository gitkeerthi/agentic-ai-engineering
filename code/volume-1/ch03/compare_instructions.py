"""Chapter 3 demo: the same model, tools and task, with two different sets of instructions."""

import sys

from investigate import INSTRUCTIONS as DETAILED
from loop import run_agent

MINIMAL = "You are a helpful logistics assistant."

task = sys.argv[1] if len(sys.argv) > 1 else "Shipment SH-4471 is three days late. Find out why."
print(f"Task: {task}")
for label, instructions in [("Minimal instructions", MINIMAL), ("Detailed instructions", DETAILED)]:
    outcome = run_agent(instructions, task, trace=False)
    tools_called = [
        call["function"]["name"]
        for message in outcome["messages"]
        for call in message.get("tool_calls", [])
    ]
    print(f"\n=== {label}: {outcome['turns']} turns, {outcome['tokens']} tokens ===")
    print(f"Tools called: {', '.join(tools_called) or 'none'}")
    print(outcome["answer"] or "No answer: the agent hit its step limit.")
