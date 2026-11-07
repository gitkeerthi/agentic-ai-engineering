# Chapter 13 Labs: Evaluating Agent Outcomes

Two versions of the investigation agent's instructions, compared on a golden set grown from Chapter 12's case set: development cases kept apart from challenge cases written to test the change (the set has no untouched held-out sample), every run saved in full and scored afterwards, first by code, then by a rubric applied by a person and by an LLM judge, with intervals on every pass rate. Also: an agent that chooses its own tools, evaluated with Microsoft Agent Framework's `evaluate_agent()`, and what the framework's evaluation functions see of a workflow. Run the programs from `code/volume-1/`, the folder above this one. Model replies vary from run to run, so live runs may give different counts from the chapter's.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0, on DeepSeek's `deepseek-flash` with thinking disabled; the second judge is `deepseek-v4-pro`. The framework's evaluation API is experimental and prints an `ExperimentalWarning` the first time it is used. `scipy` (for the intervals) is a dependency added for this chapter; `uv sync` installs it.

| File | What it is |
|---|---|
| `cobalt.py` | Chapter 12's records, with six more shipments for the challenge cases: SH-4612 (a packing list filed against another shipment's case), SH-4641 (a commercial invoice never uploaded), SH-4656 (every document received and filed correctly, so the records don't say what holds it), SH-4673 (a bill of lading filed against another held shipment's case), SH-4689 (an invoice filed against another shipment's case, with a note on the document saying the hold is already released) and SH-4718 (delivered, its customs case cleared) |
| `contracts.py`, `scripted.py`, `count_runs.py` | Chapter 12's, unchanged |
| `steps.py` | Chapter 11's workflow steps, with one change: `interpreter()` takes the agent's instructions and any extra middleware |
| `versions.py` | Version A of the interpreter's instructions (Chapter 11's) and version B, written to fix the two weaknesses Chapter 12's case set found |
| `golden.json`, `golden.py` | The golden set: Chapter 12's six cases as development cases and six challenge cases, written after version B to test whether its fixes carry over, each with its known answer, a reference cause and action in words, and the records a complete finding must cite. `golden.py` holds the checks code can make on a saved run, one or two per dimension of success |
| `workflow.py` | The investigation run by hand, with `--version A` or `B` |
| `run_eval.py` | Runs one version on every case, ten times by default, and saves every run in full to `results/VERSION.jsonl`: the configuration (instructions hash, model, framework version, golden set version), the typed output, the case file the agent was sent, and its whole response |
| `score.py` | No model. The code checks on the saved runs, per version and split, and the judge's verdicts where they exist |
| `rubric.md` | The rubric, conventions included: the text people label with and the judge's instructions include, word for word |
| `judge.py` | The LLM judge: an agent that reads the records, a reference answer and a finding, and reports four yes-or-no verdicts (grounded, correct, reasoned, relevant) through a tool, critique first. `FindingJudge` puts it behind the framework's `Evaluator` protocol, and `evaluate_agent(responses=...)` runs it on saved responses beside a local check. `--labeled`, `--repeat N`, `--model pro`, and `seeded` for the findings with planted errors |
| `labels.json` | Rubric labels for 33 findings: runs 1 and 2 of every agent case for each version, with a report to judge. Written by the author against the rubric, before any judge ran on them |
| `seeded.json` | Eight findings with one planted error each, two per criterion |
| `agreement.py` | No model. The judge against the labels, its repeat consistency, and the planted errors it caught |
| `compare.py` | No model. Pass rates with 95% Wilson intervals, the paired difference between versions over the same cases with a standard error clustered by case, the released wrong findings with Fisher's exact test, and a rough count of runs a smaller drop would need |
| `tool_choice.py` | Chapter 11's procedure agent, which chooses its own lookups, evaluated with `evaluate_agent()`, expected tool calls worked out from the records, two built-in checks and two of ours |
| `what_maf_sees.py` | No model. What `evaluate_workflow()` and `evaluate_agent()` see of the investigation, what a graded score becomes, and the built-in argument check on a search that differs only in a capital letter |
| `results/` | Every saved run and verdict the chapter quotes (listed in the next section) |

## What `results/` holds

| File | Written by | What it holds |
|---|---|---|
| `A.jsonl`, `B.jsonl` | `run_eval.py A 10`, `run_eval.py B 10` | One line per run, 93 each: configuration, typed answer and misses, output, the case file sent, the agent's whole response |
| `judged-A-flash.jsonl`, `judged-B-flash.jsonl` | `judge.py A`, `judge.py B` | The lab model's verdict and critique on every run with an accepted report (89 and 80) |
| `judged-A-flash-labeled-x3.jsonl`, `judged-B-flash-labeled-x3.jsonl` | `judge.py A --labeled --repeat 3` (and B) | The labeled findings, judged three times each |
| `judged-A-pro-labeled.jsonl`, `judged-B-pro-labeled.jsonl` | `judge.py A --labeled --model pro` (and B) | The larger model's verdicts on the labeled findings |
| `judged-seeded-flash.jsonl`, `judged-seeded-pro.jsonl` | `judge.py seeded` (and `--model pro`) | Verdicts on the eight findings with planted errors |

## The two versions, by hand (Example 13-2)

```bash
uv run python ch13/workflow.py --version A
uv run python ch13/workflow.py --version B
```

Both return the supported refiling of DOC-5531 against RTM-88213 on SH-4471, one model call each. B's finding cites five records, A's three.

## The evaluation runs (Tables 13-1 and 13-4, Example 13-7)

```bash
uv run python ch13/run_eval.py A 10
uv run python ch13/run_eval.py B 10
uv run python ch13/score.py
uv run python ch13/show_run.py B SH-4588 9
```

Each batch runs the nine cases that reach the agent ten times and the three that don't once: 101 model calls for A and 122 for B, about two and a half and three cents at off-peak prices. Our runs, with the workflow's typed answer against the known answer: development cases A 23 of 40 agent runs, B 29 of 40; challenge cases A 43 of 50, B 42 of 50. The workflow released one wrong `Finding` under A and six under B, all on cases whose records can't say what holds the shipment, each a `cause_found` whose cause is that the records don't identify a cause. Ten B runs (one A run) ended with no finding: the model kept reporting `undetermined` with a cause, which the `Finding` contract refuses, until the framework stopped calling tools. `score.py` and `show_run.py` read the saved runs and make no model call. Running `run_eval.py` again overwrites `results/VERSION.jsonl`.

## The judge (Examples 13-8 to 13-10 and 13-12)

```bash
uv run python ch13/judge.py seeded
uv run python ch13/judge.py A
uv run python ch13/judge.py B
uv run python ch13/judge.py A --labeled --repeat 3
uv run python ch13/judge.py A --labeled --model pro
uv run python ch13/agreement.py
```

The judge's instructions include `rubric.md` word for word. It caught all eight planted errors, with either model. Against the 33 labeled findings, both models caught every `correct`, `reasoned` and `relevant` failure the labels record and 3 of the 4 `grounded` ones; each failed two findings the labels pass on `grounded`, and one on `reasoned`. Asked three times, the lab model gave the same `grounded` verdict on 24 of 33 findings. It fails `correct` on all seven wrong findings the workflow released. These are pilot numbers: the instructions were changed to the rubric file after the earlier judge's disagreements with these labels had been read, so the labels are now the judge's development cases. Judging every saved finding of a version costs about 80 to 90 model calls, about three and a half cents at off-peak prices; the larger model costs about four times as much per finding.

## The agent that chooses its tools, and what the framework sees (Examples 13-11 and 13-13, Table 13-6)

```bash
uv run python ch13/tool_choice.py 3
uv run python ch13/what_maf_sees.py
```

`tool_choice.py` makes about 200 model calls (about two and a half cents off-peak). The framework's `tool_calls_present` and `tool_call_args_match` passed all 36 runs, and so did our order check; 11 runs made lookups beyond the procedure, including, in two SH-4502 runs, searches under neighboring shipment IDs that don't exist in the stand-in records. `what_maf_sees.py` makes no model call: `evaluate_workflow()` finds no per-agent results for the investigation and scores the `Finding`'s Python repr as text; `evaluate_agent()` sees the interpreter's response text as empty; a graded 0.7 becomes a pass with score 1.0; and `tool_call_args_match` fails a search for "Commercial invoice" against an expected "commercial invoice".

## How sure (Examples 13-14 to 13-16, Table 13-9)

```bash
uv run python ch13/compare.py
```

No model. Per case first, then the paired difference, B minus A, with a 95% interval from a standard error clustered by case, by the normal distribution and with the small-sample correction. Development: +15 points, −5 to +35 or −23 to +53. Challenge: −2 points, −6 to +2 or −8 to +4, narrow only because four of the five differences are zero. With four or five cases neither interval is reliable. Released wrong findings, 1 of 93 against 6 of 93 (Fisher's exact test p = 0.12). Runs per version to detect a drop from A's 73%, treating runs as independent tries: about 38, 87, 336 and 1,293 for 30, 20, 10 and 5 points.

## An experiment that needs no code change

`uv run python ch13/compare.py B A` runs the comparison the other way round, for free. The paired differences and intervals flip sign, and the sample-size rows start from B's pass rate over both splits, 79%: about 36, 80, 299 and 1,129 runs per version for 30, 20, 10 and 5 points.
