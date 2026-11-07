"""Chapter 13 demo: run one version of the investigation on every case in the golden set, several times, and
save every run in full for scoring later.

    uv run python ch13/run_eval.py VERSION [REPEATS]

VERSION is A or B (versions.py). Each run is saved as one line of ch13/results/VERSION.jsonl: the
configuration (instructions hash, model, framework version, golden set version), the workflow's typed output and its misses,
the case file the agent was sent, and the agent's whole response. A case that ends before the agent step makes
no model call, so it runs once. Prints one line per run and a score per case.
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from agent_framework import __version__ as framework_version
from agent_framework import agent_middleware

from agentlab.llm import MODEL
from agentlab.usage import mark, since
from golden import CASES, GOLDEN, answer, misses
from steps import Flagged, interpreter, investigation
from versions import VERSIONS

version, repeats = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10
instructions = VERSIONS[version]
kept = []  # the agent's runs in this workflow run: (message sent, response)


@agent_middleware
async def keep_run(context, call_next) -> None:
    await call_next()
    kept.append((context.messages[-1].text, context.result))  # ①


agent = interpreter(instructions=instructions, middleware=[keep_run])
configuration = {
    "version": version,
    "instructions_md5": hashlib.md5(instructions.encode()).hexdigest(),  # ②
    "model": MODEL,
    "framework": framework_version,
    "golden_set": GOLDEN["version"],
}
results = Path(__file__).parent / "results" / f"{version}.jsonl"


def saved_form(output) -> dict:
    if not isinstance(output, Flagged):
        return output.model_dump()
    finding = output.finding.model_dump() if output.finding else None
    return {"reason": output.reason, "finding": finding, "problems": output.problems}


async def main() -> None:
    start = mark()
    results.parent.mkdir(exist_ok=True)
    with results.open("w") as saved:
        for case in CASES:
            matched = runs = 0
            for run in range(1, repeats + 1):
                kept.clear()
                calls = mark()
                [output] = (
                    await investigation(agent).run(case["shipment_id"])
                ).get_outputs()
                typed = answer(output)
                query, response = kept[-1] if kept else (None, None)
                record = {
                    **configuration,
                    "case": case["case"],
                    "shipment_id": case["shipment_id"],
                    "split": case["split"],
                    "run": run,
                    "answer": typed,
                    "misses": misses(case, typed),
                    "output": saved_form(output),
                    "query": query,
                    "response": response.to_dict() if response else None,  # ③
                    "model_calls": mark() - calls,
                }
                saved.write(json.dumps(record) + "\n")
                runs += 1
                matched += not record["misses"]
                print(
                    f"{case['shipment_id']} run {run}: {typed}"
                    + (f"  misses: {record['misses']}" if record["misses"] else "")
                )
                if (
                    record["model_calls"] == 0
                ):  # no model call: every run would be the same
                    break
            print(
                f"=== {case['shipment_id']} ({case['split']}): {matched} of {runs}\n"
            )
    print(f"Configuration: {configuration}")
    print(f"Saved: {results.relative_to(Path.cwd())}")
    print(f"Cost: {since(start)}")


asyncio.run(main())
