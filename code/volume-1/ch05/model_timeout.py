"""Chapter 5 demo: a timeout and a retry count on the model client. How long does a model call that times out hold the run?

Run it with a timeout far below what a model call takes, such as 0.1 seconds, and every attempt times out.
At half a second, a short reply sometimes arrives in time, and the next model call times out instead.
"""

import argparse
import asyncio
import logging
import sys
import time

from agent_framework import Agent

from agentlab.llm import make_client
from cobalt import TOOLS
from investigate import INSTRUCTIONS, TASK

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--timeout", type=float, required=True, help="seconds the OpenAI library waits for the provider's answer")
parser.add_argument("--retries", type=int, required=True, help="attempts the OpenAI library makes after the first")
args = parser.parse_args()

# The OpenAI library logs each retry it makes.
logging.basicConfig(stream=sys.stdout, format="%(message)s")
logging.getLogger("openai._base_client").setLevel(logging.INFO)

agent = Agent(make_client(timeout=args.timeout, max_retries=args.retries), INSTRUCTIONS, name="investigator", tools=TOOLS)

print(f"Task: {TASK}  (model client: timeout {args.timeout:g} seconds, {args.retries} {'retry' if args.retries == 1 else 'retries'})\n")
start = time.monotonic()
try:
    result = asyncio.run(agent.run(TASK))
    print(result.text)
except Exception as error:
    print(f"\nThe run raised {type(error).__name__}: {error}")
    if error.__cause__:
        print(f"  caused by {type(error.__cause__).__name__}: {error.__cause__}")
print(f"The program waited {time.monotonic() - start:.1f} seconds for the run.")
