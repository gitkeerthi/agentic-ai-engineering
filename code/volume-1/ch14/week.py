"""Chapter 14 experiment: the observed investigation run on every case in the golden set, several times, as a
stand-in for a week of production runs. Every run leaves its trace, its case record and its evidence.

    uv run python ch14/week.py STORE [--version A|B] [--model lab|larger] [--runs N] [--langfuse]

A case that ends before the agent step makes no model call, so it runs once. Prints one line per run. With
--langfuse, every span goes to the local Langfuse as well (to_langfuse.py).
"""

import argparse
import asyncio

import telemetry
from agentlab.llm import make_client
from agentlab.usage import mark, since
from golden import CASES
from show import case_line
from steps import interpreter, investigation
from versions import VERSIONS

MODELS = {"lab": "deepseek-flash", "larger": "deepseek-v4-pro"}

parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("store")
parser.add_argument("--version", choices=VERSIONS, default="A")
parser.add_argument("--model", choices=MODELS, default="lab")
parser.add_argument("--runs", type=int, default=10)
parser.add_argument("--langfuse", action="store_true")
args = parser.parse_args()

store = telemetry.setup(args.store, langfuse=args.langfuse)
client = make_client(model=MODELS[args.model])
agent = interpreter(
    client,
    instructions=VERSIONS[args.version],
    middleware=[telemetry.keep_evidence],
)


async def main() -> None:
    start = mark()
    for case in CASES:
        for run in range(1, args.runs + 1):
            calls = mark()
            record = await telemetry.investigate(
                investigation(agent), agent, case["shipment_id"]
            )
            print(case_line(record)[13:].replace("\n ", ""))
            if mark() == calls:  # no model call: every run would be the same
                break
    print(f"Cost: {since(start)}")


asyncio.run(main())
telemetry.close()
