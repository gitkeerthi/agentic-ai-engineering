# Chapter 15 Labs: Project 1, An Evaluated Exception Research Agent

Chapter 15 assembles the earlier chapters' ideas into one application that runs on one machine: Cobalt's exception research agent. The application lives in the package `cobalt_exceptions/` in `code/volume-1/`, which later project chapters extend; its tests are in `tests/`. This folder holds the programs the chapter runs: the evaluation, its scoring, the designed failures, and a trace reader. Run everything from `code/volume-1/`, the folder above this one.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0. When the code is corrected, the chapter is corrected with it, so its listings describe the code in this repository; `uv sync --locked` installs exactly the dependencies they were run with.

## The application

| Path | What it is |
|---|---|
| `cobalt_exceptions/domain/` | No framework code. `contracts.py`: the investigation request, the finding (with its typed `fault` and `open_question`), the case file, the flag. `procedure.py`: where each read can end the investigation, and every check a finding must pass. `lifecycle.py`: the case states, the moves allowed between them and who may make each. `approval.py`: the refiling request, its comparison with the finding, and who may answer it |
| `cobalt_exceptions/systems/` | Stand-ins for Cobalt's systems of record, each behind the client a real system would have: transport records, customs and the document store's reads (`records.py`, seeded from `seed.json`, with retries and lab faults), the store's write (`filing.py`), the message archive (`messages.py`), the case system (`cases.py`) and the approval queue (`approvals.py`). They keep their data as JSON files in the state folder |
| `cobalt_exceptions/services/` | No framework code. `casework.py`: opens a case, records how an investigation ended, closes a filed case when customs clears it. `gate.py`: the refiling gate |
| `cobalt_exceptions/agents/` | The Microsoft Agent Framework adapters. `steps.py`: the workflow (three reads, one agent step, one check). `interpreter.py`: the agent, its instructions, the `CaseFileContext` provider, the `search_messages` and `report_finding` tools, its middleware and loop limits. `telemetry.py`: Chapter 14's tracing, run record and evidence store |
| `cobalt_exceptions/cli.py` | The `cobalt` command |
| `cobalt_exceptions/evaluated.json` | The configuration the evaluation approved, written by `ch15/score.py --release` |
| `tests/` | The application's tests: no model call, except one live test |

The dependency rule (each layer imports only the layers beneath it; the domain, systems and services never import the framework or the model client; only the services may file) is in `pyproject.toml` under `[tool.importlinter]`. Check it with `uv run lint-imports`; `tests/test_layers.py` runs the same check.

## This folder

| File | What it is |
|---|---|
| `golden.json`, `golden.py` | Chapter 13's golden set with the typed fault in each expected `cause_found`, and three cases written with this chapter's design (SH-4731, SH-4746, SH-4759); the comparison of a run's typed output with a case's known answer |
| `evaluate.py` | Every golden case N times, each run saved in full with its configuration, usage and cost, in `store/NAME/` |
| `score.py` | Scores a saved batch: per-case results with intervals, released wrong findings, cost; `--baseline` scores Chapter 14's saved week batch on the shared cases; `--release` records the evaluated configuration |
| `failures.py` | Twenty-two designed failures, each run once with scripted replies and lab faults. No model call |
| `trace.py` | One investigation read back from its trace, evidence and case record. No model call |

`store/eval/` holds the evaluation batch the chapter quotes (runs, spans, logs, metrics, evidence); it is committed so that scoring and reconstruction cost nothing.

## Running the application

```bash
uv run cobalt reset
uv run cobalt investigate SH-4471 --as analyst-017
uv run cobalt review
uv run cobalt decide REQ-0001 --as analyst-017 --approve   # refused: not an approver
uv run cobalt decide REQ-0001 --as lead-031 --approve
uv run cobalt customs        # lab stand-in: customs processes the filing
uv run cobalt status SH-4471
uv run python ch15/trace.py <trace ID the investigation printed> --evidence
```

The investigation found the misfiled invoice and named the refiling; the gate turned it into REQ-0001 and the case became `proposed`. `analyst-017` is refused, and the refusal names the rule ("only approvers may approve refilings, and analyst-017 isn't one"); `lead-031`'s approval filed it as FIL-001, and the case waited at `filed` until the customs stand-in cleared RTM-88213. In the run the chapter quotes the agent searched twice in one model call and reported in the next: two model calls, $0.00081. In an earlier run its first report cited `MS-7001`, the contract refused it, and its second report was accepted. Try `uv run cobalt investigate SH-4731 --as analyst-017` (the cause is in a customs message) and `SH-4588` (the records don't say).

## The evaluation, the failures, the tests

```bash
uv run python ch15/evaluate.py mine --runs 10          # about $0.09; writes ch15/store/mine/
uv run python ch15/score.py eval --baseline ../ch14/store/week   # the chapter's batch
uv run python ch15/failures.py
uv run pytest tests
uv run lint-imports
```

In the batch the chapter quotes (123 runs, 257 model calls, $0.087 at peak prices) no wrong finding left the workflow. Twelve of the fifteen cases were right in every run. SH-4588 was right in 3 of 10 runs and SH-4759 in 4 of 10; every wrong run on them named a packing list "not uploaded" for a case that doesn't require one, and the fault check flagged it. SH-4502's one wrong run cited two documents that don't exist, and the provenance check flagged it. Three earlier batches of the same instructions and tools, made before later fixes to the gate, the lifecycle and the filing module, put SH-4588 at 3, 7 and 5 of 10: per-case rates from ten runs move by several runs from batch to batch. On the twelve cases Chapter 14's week batch also ran, scored on the fields both contracts share, Chapter 14's system was right in 69 of 93 runs and released 2 wrong findings; this one was right in 85 of 93 and released none. The two systems differ in several ways at once (the search tool, the contract, the instructions, the provider), so the comparison can't say which change did it.

`failures.py` prints the designed outcome of each of its twenty-two failures. `pytest tests` runs 62 tests and skips the live one (`uv run pytest tests -m live` runs it, about $0.001). `lint-imports` checks three contracts: each layer imports only the layers beneath it; the domain, systems and services never import the framework or the model client; only the services may import the store's write (`systems/filing.py`).

## Known limitations

- The stand-in systems are JSON files with no locking; run one command at a time.
- `TokenBudget` adds the usage each model call reports; a client that reports none would never trip it (Chapter 8 noted the same of its copy).
- The 60-second limit is cooperative: a blocking read or a tool already running finishes first.
- The approver list and the `--as` names are plain strings; nothing verifies them.
