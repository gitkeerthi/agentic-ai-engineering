# Chapter 11 Labs: Basic Workflows

Cobalt's procedure for a customs hold over documents, two ways. First written into the investigation agent's instructions, where the model still chooses every step; then as a workflow, where code reads the records in the procedure's order, one agent step interprets them, and a last step checks the agent's finding against what it was shown. The programs also show what the workflow builder checks and what it lets through, a test that reaches every ending, what an agent added to a workflow as it is yields and carries between runs, what can be shared between runs, and what the caller receives when a step fails. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different outcome, from the chapter's.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0, on DeepSeek's `deepseek-flash` with thinking disabled. The graph workflow API (`WorkflowBuilder`, `Executor`, `@executor`, `@handler`) is stable in this version; the functional API (`@workflow`, `@step`) is experimental and prints a warning.

| File | What it is |
|---|---|
| `cobalt.py` | Chapter 10's records and four read tools. Each tool now calls a plain function (`shipment_status`, `customs_case`, `required_documents`, `document_search`) that returns a copy of the record, and the workflow's steps call the same functions. `make_store_busy()` and `reset()` |
| `contracts.py` | Chapter 10's `Finding` contract and `record_problems()`, unchanged |
| `procedure_agent.py` | Chapter 10's agent with the procedure written into its instructions, reporting its finding with `report_finding`. Prints the path it took, the finding and what the run cost. `--store-busy`, `--trace` |
| `steps.py` | The workflow: message types (`CustomsShipment`, `OpenCase`, `CaseFile`, `Proposed`), the `Flagged` output with a `reason` a caller can route on, the one hold reason the procedure covers (`DOCUMENT_HOLDS`, checked by `covered()`), the step classes `LoadShipment`, `LoadCase`, `CheckDocuments`, `Interpret` (an agent with one tool, `report_finding`) and `CheckFinding`, `reads()`, and `investigation(agent)`, which builds new executors and a new workflow for each request around a shared agent |
| `pipeline.py` | No model. The three reads and a `hand_over` step (written with `@executor`) connected with `add_edge`; prints every event of the run and its output |
| `workflow.py` | The investigation workflow: the reads, the agent step and the check. Prints the steps run, the finding and what the run cost, or, when the store or the model call fails, the exception (`StoreUnavailable` or the framework's `ChatClientException`). `--store-busy`, `--trace` |
| `wiring.py` | No model. Five wiring mistakes: two the builder refuses, two that build and drop a message silently (read from the run's spans), and an input of the wrong type |
| `failed_step.py` | No model. The store busy, with the run's events streamed; then the agent step's model call failing (a scripted client that raises) |
| `agent_executor.py` | No model. An agent added to the chain as it is, so the framework wraps it in `AgentExecutor`, with a step after it that reads the reply; the same workflow instance run twice, then a new one built with `output_from` |
| `scripted.py` | A lab-only client that replies from a script, or raises an exception the script names, instead of calling a model |
| `test_endings.py` | No model. A pytest test that runs the investigation once for each of its 15 endings and asserts one output: a `Finding` with the expected status, or a `Flagged` with the expected reason and problem, plus two tests that a busy store and an unreachable model raise |
| `instances.py` | No model. The same workflow run twice (what the agent is sent), a second run while the first is going, and four workflows run at once with one shared executor and with an executor each |
| `functional.py` | No model. The same reads with the experimental functional API |
| `count_runs.py` | Runs a program several times, counts the outcomes it reports, and averages the model calls, tokens and seconds |

The SH-5120 task used below is `"Shipment SH-5120 is due next Wednesday. Is anything holding it up?"`.

## The procedure in the instructions

```bash
uv run python ch11/count_runs.py 10 ch11/procedure_agent.py
uv run python ch11/count_runs.py 10 ch11/procedure_agent.py "Shipment SH-5120 is due next Wednesday. Is anything holding it up?"
uv run python ch11/count_runs.py 5 ch11/procedure_agent.py --store-busy
uv run python ch11/procedure_agent.py --trace
```

On SH-4471, all 10 runs took the procedure's seven lookups in order and proposed refiling DOC-5531 against RTM-88213, at 6.0 model calls, 10,503 input tokens and 8.6 seconds a run on average. On SH-5120 (two batches of 10), all 20 runs looked up the shipment, stopped, and reported nothing wrong: 2.0 model calls a run. With the store busy (two batches of 5), 9 of 10 runs searched 10 to 21 times and hit the iteration limit with no finding; their last, tools-off call came back as more search requests written as text. One run searched 9 times and reported `undetermined`, recommending the searches be re-run. Average 9.7 model calls and 19,622 input tokens. With `--trace`, the six model calls of an SH-4471 run read 1,419, 1,524, 1,620, 1,733, 2,042 and 2,138 tokens.

## The procedure as a workflow

```bash
uv run python ch11/pipeline.py SH-4471
uv run python ch11/pipeline.py SH-5120
uv run python ch11/pipeline.py SH-9999
uv run python ch11/count_runs.py 10 ch11/workflow.py
uv run python ch11/count_runs.py 3 ch11/workflow.py SH-5120
uv run python ch11/workflow.py --trace
```

`pipeline.py` runs SH-4471 in four supersteps, one step in each, and outputs the `CaseFile` with the invoice filed against RTM-88124; SH-5120 ends at the first step with a `nothing_wrong` finding, and SH-9999 with a `Flagged` result. Every final state is `IDLE`. The investigation workflow found the misfiled invoice and passed its check in 10 of 10 runs, at one model call, 1,305 input tokens, 390 output tokens and 2.3 seconds a run on average; nine runs had 1,152 input tokens cached, and the first, just after the instructions changed, had none. SH-5120 needs no model call. The trace shows `workflow.build` at 0.00 s, and the agent's `invoke_agent`, one `chat` and `execute_tool` spans inside the `interpret` step.

## What the builder checks

```bash
uv run python ch11/wiring.py
```

An edge between steps whose types don't match raises `TypeCompatibilityError`, and steps no path reaches raise `GraphConnectivityError`. With the last edge left out, the run ends `IDLE` with no output; the case file was sent and no edge delivered it (the framework logs a dead end at INFO when building). With a step that sends a `dict` where it declared `CustomsShipment`, the run ends `IDLE` with no output, and the edge span records `dropped type mismatch`. `run(4471)` is refused: the start step accepts `str`. A static type checker catches the `dict` before the run: `uvx pyright --pythonpath .venv/bin/python ch11/wiring.py` reports that a `dict[str, str]` can't be passed where `send_message()` expects a `CustomsShipment` (its other three reports are about the program's span-reading code).

## Every ending, tested

```bash
uv run pytest ch11/test_endings.py -v
```

Fifteen endings, each run once with scripted agent replies: a supported finding passes; `nothing_wrong` comes only from Cobalt's rule (SH-5120, and SH-4471 changed to delivered with its case cleared); evidence citing SH-0042, a refiling against RTM-88124, an `undetermined` finding, a `nothing_wrong` finding from the agent and an answer in text are flagged; an unknown shipment, a held shipment with no customs case, a customs case on hold for another reason (a physical inspection), a held shipment whose customs case has cleared, a customs case not on file, a case with no list of required documents and a document filed against a case not on file are flagged before the agent step. A busy store raises `StoreUnavailable` and an unreachable model raises `ConnectionError` (the scripted client raises it bare; the real chat client wraps it in `ChatClientException`). 17 passed in 0.38 s.

## An agent added as it is, and what can be shared

```bash
uv run python ch11/agent_executor.py
uv run python ch11/instances.py
```

The wrapped agent yields its `AgentResponse` as a workflow output, so with a step after it each run has two outputs; a workflow built with `output_from=[read_reply]` has one. Run twice on the same workflow instance, the second run sent the agent three messages (the first run's case file and reply, then the new one); a newly built workflow sent one. In `instances.py`, `Interpret` sends the agent one message on each run of a reused workflow; a second run while the first is going raises `WorkflowException`; and four workflows run at once took 2.01 s sharing one `@executor` function's object and 0.51 s with an executor instance each.

## When a step fails

```bash
uv run python ch11/failed_step.py
uv run python ch11/workflow.py --store-busy
```

With the store busy, the stream reports `executor_failed` for `check_documents`, then `failed` and the state `FAILED`, and the caller receives `StoreUnavailable`. With the agent step's model call failing, the stream reports `executor_failed` for `interpret`, and the caller receives the `ConnectionError`. The full workflow with the store busy stops with `StoreUnavailable` and no model call. With the model endpoint unreachable (we blocked it with a proxy on a closed port and an invalid key, so no request left the machine), `workflow.py` stops with `ChatClientException` and no finding.

## The same reads as a functional workflow

```bash
uv run python ch11/functional.py
```

An `ExperimentalWarning`, one `executor_invoked` and `executor_completed` pair for each `@step` call, and the function's return value as the output.
