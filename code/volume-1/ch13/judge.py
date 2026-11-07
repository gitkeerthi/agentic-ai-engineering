"""Chapter 13 demo: a first LLM judge for what code can't score, the wording of each finding.

    uv run python ch13/judge.py VERSION [--model flash|pro] [--labeled] [--repeat N]
    uv run python ch13/judge.py seeded [--model flash|pro]

The judge is an agent that reads what the investigating agent was given, a person's reference answer, and the
finding, and reports four yes-or-no verdicts through a tool, critique first. Its instructions carry rubric.md,
the text the people who label findings use, word for word. FindingJudge wraps it in Microsoft
Agent Framework's Evaluator protocol, so evaluate_agent() runs it on saved responses, beside a local check.

VERSION judges every saved run of that version (ch13/results/VERSION.jsonl) that has an accepted report;
--labeled only the runs in labels.json; --repeat judges each one N times. "seeded" judges the findings with
planted errors in seeded.json. Verdicts are saved to ch13/results/judged-*.jsonl.
"""

import argparse
import asyncio
import json
from pathlib import Path

from agent_framework import (
    Agent,
    AgentResponse,
    Content,
    EvalItemResult,
    EvalResults,
    EvalScoreResult,
    FunctionTool,
    LocalEvaluator,
    Message,
    MiddlewareTermination,
    evaluate_agent,
    evaluator,
    function_middleware,
)
from pydantic import BaseModel, Field

from agentlab.llm import make_client
from agentlab.usage import mark, since
from golden import CASES, CRITERIA
from steps import interpreter

MODELS = {"flash": "deepseek-flash", "pro": "deepseek-v4-pro"}

RUBRIC = (Path(__file__).parent / "rubric.md").read_text()  # the labelers' text

JUDGE_INSTRUCTIONS = f"""\
You check one finding written by an agent that investigates held shipments for
Cobalt Freight. You get the records the agent was given, a reference answer written
by a person who knows the case, and the agent's finding.

{RUBRIC}
Write the critique first: one or two sentences per question, naming the records.
Then call report_verdict once."""


class Verdict(BaseModel):
    critique: str = Field(
        description="One or two sentences per question, written first"
    )
    grounded: bool
    correct: bool
    reasoned: bool
    relevant: bool


def record_verdict(**verdict) -> str:
    """Report the verdict on the finding."""
    return "Recorded."


@function_middleware
async def stop_after_verdict(context, call_next) -> None:
    await call_next()
    if context.function.name == "report_verdict":
        raise MiddlewareTermination("verdict recorded", result=context.result)


def judge_agent(model: str) -> Agent:
    report_verdict = FunctionTool(
        name="report_verdict",
        description=record_verdict.__doc__,
        func=record_verdict,
        input_model=Verdict,
    )
    client = make_client(model=model)
    client.function_invocation_configuration["max_iterations"] = 3
    return Agent(
        client,
        JUDGE_INSTRUCTIONS,
        name="judge",
        tools=[report_verdict],
        middleware=[stop_after_verdict],
    )


def reported_arguments(conversation: list[Message], tool: str) -> dict | None:
    """The arguments of the last call to `tool` that the framework accepted."""
    accepted = {
        c.call_id
        for m in conversation
        for c in m.contents
        if c.type == "function_result" and c.result == "Recorded."
    }
    calls = [
        c
        for m in conversation
        for c in m.contents
        if c.type == "function_call" and c.name == tool and c.call_id in accepted
    ]
    return json.loads(calls[-1].arguments) if calls else None


class FindingJudge:
    """A judge behind the framework's Evaluator protocol: one model call per item, four scores."""

    def __init__(self, model: str, at_once: int = 6):
        self.name = f"Judge ({model})"
        self.agent = judge_agent(model)
        self.limit = asyncio.Semaphore(at_once)

    async def verdict(self, item) -> Verdict | None:
        async with self.limit:
            return await self._verdict(item)

    async def _verdict(self, item) -> Verdict | None:
        reference = json.loads(item.expected_output)["reference"]
        finding = reported_arguments(item.conversation, "report_finding")
        message = (
            f"Records the agent was given:\n{item.query}\n\n"  # ①
            f"Reference answer:\nCause: {reference['cause']}\n"
            f"Action: {reference['action']}\n\n"
            f"The agent's finding:\n{json.dumps(finding, indent=2)}"
        )
        result = await self.agent.run(message)
        arguments = reported_arguments(result.messages, "report_verdict")
        return Verdict.model_validate(arguments) if arguments else None

    async def evaluate(self, items, *, eval_name: str = "Judge") -> EvalResults:
        verdicts = await asyncio.gather(*(self.verdict(item) for item in items))
        results, passed = [], 0
        for index, (item, verdict) in enumerate(zip(items, verdicts)):
            if (
                verdict is None
            ):  # the judge reported nothing usable: an error, not a fail
                results.append(EvalItemResult(item_id=str(index), status="error"))
                continue
            scores = [
                EvalScoreResult(
                    name=criterion,
                    score=float(getattr(verdict, criterion)),
                    passed=getattr(verdict, criterion),
                    sample={"critique": verdict.critique},
                )
                for criterion in CRITERIA
            ]
            ok = all(s.passed for s in scores)
            passed += ok
            results.append(
                EvalItemResult(
                    item_id=str(index),
                    status="pass" if ok else "fail",
                    scores=scores,
                )
            )
        errored = sum(r.status == "error" for r in results)
        return EvalResults(
            provider=self.name,
            run_id=eval_name,
            result_counts={
                "passed": passed,
                "failed": len(items) - passed - errored,
                "errored": errored,
            },
            items=results,
        )


@evaluator
def cites_key_records(conversation: list, expected_output: str) -> bool:
    """A check code can make, run beside the judge: the finding cites the records its answer rests on."""
    finding = reported_arguments(conversation, "report_finding") or {"evidence": []}
    cited = {e["record_id"] for e in finding["evidence"]}
    return set(json.loads(expected_output)["must_cite"]) <= cited


def seeded_response(finding: dict) -> AgentResponse:
    """A saved-response shape for a finding written by hand: one accepted report_finding call."""
    call = Content.from_function_call(
        call_id="seeded", name="report_finding", arguments=json.dumps(finding)
    )
    done = Content.from_function_result(call_id="seeded", result="Recorded.")
    return AgentResponse(
        messages=[Message("assistant", [call]), Message("tool", [done])]
    )


parser = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
parser.add_argument("version", help="A, B or seeded")
parser.add_argument("--model", choices=MODELS, default="flash")
parser.add_argument("--labeled", action="store_true")
parser.add_argument("--repeat", type=int, default=1)
args = parser.parse_args()

here = Path(__file__).parent
by_id = {case["shipment_id"]: case for case in CASES}
if args.version == "seeded":
    seeded = json.loads((here / "seeded.json").read_text())
    rows = [
        {
            "shipment_id": s["shipment_id"],
            "run": s["id"],
            "split": "seeded",
            "plants": s["plants"],
        }
        for s in seeded
    ]
    sent = {  # the case file each shipment's agent was sent, from a saved run
        r["shipment_id"]: r["query"]
        for line in (here / "results" / "A.jsonl").read_text().splitlines()
        if (r := json.loads(line))["query"]
    }
    queries = [sent[s["shipment_id"]] for s in seeded]
    responses = [seeded_response(s["finding"]) for s in seeded]
else:
    saved = [
        json.loads(line)
        for line in (here / "results" / f"{args.version}.jsonl")
        .read_text()
        .splitlines()
    ]
    saved = [
        r
        for r in saved
        if r["response"]
        and reported_arguments(
            AgentResponse.from_dict(r["response"]).messages, "report_finding"
        )
    ]
    if args.labeled:
        labeled = {
            (label["shipment_id"], label["run"])
            for label in json.loads((here / "labels.json").read_text())
            if label["version"] == args.version
        }
        saved = [r for r in saved if (r["shipment_id"], r["run"]) in labeled]
    rows = [{k: r[k] for k in ("shipment_id", "run", "split")} for r in saved]
    queries = [r["query"] for r in saved]
    responses = [AgentResponse.from_dict(r["response"]) for r in saved]
expected = [
    json.dumps({k: by_id[row["shipment_id"]][k] for k in ("reference", "must_cite")})
    for row in rows
]

name = f"judged-{args.version}-{args.model}" + ("-labeled" if args.labeled else "")
name += f"-x{args.repeat}" if args.repeat > 1 else ""


async def main() -> None:
    start = mark()
    out = []
    for repeat in range(1, args.repeat + 1):
        local, judged = await evaluate_agent(
            agent=interpreter(),  # only for its tool definitions; nothing is rerun
            responses=responses,
            queries=queries,
            expected_output=expected,
            evaluators=[
                LocalEvaluator(cites_key_records),
                FindingJudge(MODELS[args.model]),
            ],
        )  # ①
        print(
            f"Repeat {repeat}: {local.provider} {local.passed}/{local.total} passed; "
            f"{judged.provider} {judged.passed}/{judged.total} passed all four, "
            f"{judged.result_counts['errored']} errored"
        )
        for row, item in zip(rows, judged.items):
            verdict = {s.name: s.passed for s in item.scores}
            critique = item.scores[0].sample["critique"] if item.scores else None
            out.append(
                {**row, "repeat": repeat, "verdict": verdict, "critique": critique}
            )
            marks = " ".join(
                f"{c}={'yes' if verdict.get(c) else 'no'}" for c in CRITERIA
            )
            print(
                f"  {row['shipment_id']} run {row['run']}: {marks if item.scores else 'error'}"
            )
            if item.scores and not all(verdict.values()):
                print(f"    critique: {critique}")
    (here / "results" / f"{name}.jsonl").write_text(
        "".join(json.dumps(o) + "\n" for o in out)
    )
    print(f"\nSaved: ch13/results/{name}.jsonl")
    print(f"Cost: {since(start)}")


asyncio.run(main())
