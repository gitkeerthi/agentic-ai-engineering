"""Chapter 3 demo: a task that states something false, with and without an instruction to check the task's claims."""

import sys

from investigate import INSTRUCTIONS
from loop import run_agent

CHECK_CLAIMS = """

Before investigating, check the task's claims against the systems. If the systems
contradict the task (for example, the shipment is not late), say so and stop."""

task = sys.argv[1] if len(sys.argv) > 1 else "Shipment SH-5120 is late. Find out why."
note = "" if len(sys.argv) > 1 else "   (SH-5120 is due next Wednesday)"
print(f"Task: {task}{note}")
for label, instructions in [("Without the check", INSTRUCTIONS), ("With the check", INSTRUCTIONS + CHECK_CLAIMS)]:
    outcome = run_agent(instructions, task, trace=False)
    print(f"\n=== {label}: {outcome['turns']} turns ===")
    print(outcome["answer"] or "No answer: the agent hit its step limit.")
