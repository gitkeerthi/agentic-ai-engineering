"""Chapter 3 demo: the SH-4471 investigation agent, turn by turn."""

import argparse

from loop import run_agent

INSTRUCTIONS = """\
You investigate delayed shipments for Cobalt Freight's operations team.

Goal: find the root cause of a delay and the action that would fix it.

How to work:
- Use the tools to check facts. Never guess a status, case number or document location.
- Before each tool call, say in one sentence what you want to find out.
- A hold or a delay is a symptom. Keep investigating until you find what caused it,
  or until no tool can tell you more.

Limits:
- You can only read Cobalt's systems. Recommend actions; never claim to have taken one.

Answer format:
Cause: one sentence.
Evidence: the facts that show it, with IDs.
Recommended action: one sentence."""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default="Shipment SH-4471 is three days late. Find out why.")
    parser.add_argument("--max-steps", type=int, default=10, help="the loop's step limit (default 10)")
    args = parser.parse_args()
    print(f"Task: {args.task}")
    outcome = run_agent(INSTRUCTIONS, args.task, max_steps=args.max_steps)
    print(f"\n=== Final answer after {outcome['turns']} turns, {outcome['tokens']} tokens in total ===")
    print(outcome["answer"] or "No answer: the agent hit its step limit.")
