"""Chapter 4 demo: Chapter 3's answer check, reading the framework's response instead of a message list."""

import argparse
import asyncio
import re

from investigate import agent

HEADINGS = ("Cause", "Evidence", "Recommended action")
RECORD_ID = re.compile(r"\b(?:SH|RTM|DOC)-\d+\b")


def check_answer(task: str, result) -> list[str]:
    messages = result.messages
    answer = messages[-1].text
    problems = ["The reply was cut off at the output-token limit"] if result.finish_reason == "length" else []
    problems += [
        f"Missing heading: {heading}"
        for heading in HEADINGS
        if not re.search(rf"^\W*{heading}\W*:", answer, re.MULTILINE | re.IGNORECASE)
    ]
    # Where each ID first appeared: the task, a tool result or the model (its notes and its tool requests).
    first_seen = {record_id: "task" for record_id in RECORD_ID.findall(task)}
    for message in messages[:-1]:  # every message the run added except the answer itself
        for content in message.contents:
            if content.type == "function_result":
                text, source = content.result, "tool"
            elif content.type == "function_call":
                text, source = content.arguments, "model"
            else:
                text, source = content.text or "", "model"
            for record_id in RECORD_ID.findall(str(text)):
                first_seen.setdefault(record_id, source)
    for record_id in sorted(set(RECORD_ID.findall(answer))):
        source = first_seen.get(record_id)
        if source == "model":
            problems.append(f"{record_id} was first written by the model, not by the task or a tool")
        elif source is None:
            problems.append(f"{record_id} appears only in the answer")
    return problems


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("task", nargs="?", default="Shipment SH-4471 is three days late. Find out why.")
parser.add_argument("--max-iterations", type=int, help="the limit on rounds of tool calls (investigate.py sets 9)")
args = parser.parse_args()
if args.max_iterations:
    agent.client.function_invocation_configuration["max_iterations"] = args.max_iterations
print(f"Task: {args.task}\n")
result = asyncio.run(agent.run(args.task))
print(result.messages[-1].text)

problems = check_answer(args.task, result)
print("\n=== Check: " + ("passed" if not problems else "failed"))
for problem in problems:
    print(f"- {problem}")
