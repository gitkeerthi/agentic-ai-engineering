"""Chapter 3 demo: check the agent's final answer before anyone acts on it."""

import re
import sys

from investigate import INSTRUCTIONS
from loop import run_agent

HEADINGS = ("Cause", "Evidence", "Recommended action")
RECORD_ID = re.compile(r"\b(?:SH|RTM|DOC)-\d+\b")


def check_answer(answer: str, messages: list) -> list[str]:
    problems = [
        f"Missing heading: {heading}"
        for heading in HEADINGS
        if not re.search(rf"^\W*{heading}\W*:", answer, re.MULTILINE | re.IGNORECASE)
    ]
    # Where each ID first appeared: the task ("user"), a tool result ("tool") or the model ("assistant").
    first_seen = {}
    for message in messages[1:-1]:  # skip the instructions and the answer itself
        text = (message.get("content") or "") + "".join(
            call["function"]["arguments"] for call in message.get("tool_calls", [])
        )
        for record_id in RECORD_ID.findall(text):
            first_seen.setdefault(record_id, message["role"])
    for record_id in sorted(set(RECORD_ID.findall(answer))):
        source = first_seen.get(record_id)
        if source == "assistant":
            problems.append(f"{record_id} was first written by the model, not by the task or a tool")
        elif source is None:
            problems.append(f"{record_id} appears only in the answer")
    return problems


task = sys.argv[1] if len(sys.argv) > 1 else "Shipment SH-5120 is late. Find out why."
outcome = run_agent(INSTRUCTIONS, task, trace=False)
print(f"Task: {task}\n")
print(outcome["answer"] or "No answer: the agent hit its step limit.")
if outcome["answer"]:
    problems = check_answer(outcome["answer"], outcome["messages"])
    print("\n=== Check: " + ("passed" if not problems else "failed"))
    for problem in problems:
        print(f"- {problem}")
