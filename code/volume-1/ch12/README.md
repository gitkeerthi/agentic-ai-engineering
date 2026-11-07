# Chapter 12 Labs: Testing Agentic Applications

A test suite for Chapter 11's investigation workflow, one kind of test per file, and the book's first case set: held shipments with known answers, scored from the investigation's typed output. Every test except the end-to-end ones runs with no model call, so the suite is free to run on every change. Run the programs from `code/volume-1/`, the folder above this one. Model replies vary from run to run, so the live runs may give different counts from the chapter's.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0, on DeepSeek's `deepseek-flash` with thinking disabled, and with pytest 9.2, pytest-recording 0.14 (vcrpy 9.4) and syrupy 6.1. The last two are development dependencies added for this chapter: pytest-recording records and replays HTTP requests (VCR cassettes), and syrupy keeps snapshots. `uv sync` installs them.

| File | What it is |
|---|---|
| `cobalt.py` | Chapter 11's records and read functions, with four more held shipments for the case set: SH-4502 (a packing list never uploaded), SH-4533 (held for a physical inspection), SH-4560 (a bill of lading filed against another shipment's case) and SH-4588 (every document received and filed correctly, so the records don't say what holds it) |
| `contracts.py`, `steps.py` | Chapter 10's `Finding` contract and Chapter 11's workflow steps, unchanged |
| `scripted.py` | Chapter 11's scripted client, which replies from a script instead of calling a model, with one change: a call after the script runs out raises `UnexpectedModelCall`, which says so |
| `the_change.py` | The change the chapter opens with: `CarryOnCheckDocuments` keeps a failed search in the case file instead of raising `StoreUnavailable`, and `investigation_with_change()` builds the workflow with it |
| `workflow.py` | Chapter 11's program, run by hand. `--with-change`, `--store-busy` |
| `count_runs.py` | Runs a program several times and counts the outcomes it reports |
| `pytest.ini`, `conftest.py` | The `live` marker: deselected by `pytest.ini`, and skipped by `conftest.py` unless `-m live` is given, however pytest is started; a fixture that resets the records around every test; the `build` fixture, which returns the workflow builder under test, changed by `--with-change` |
| `replies.py` | Findings the tests script the agent to report, including `BUSY_STORE_FINDING`, a real reply from a run of the changed workflow with the store busy |
| `test_rules.py` | Unit tests: `record_problems()`, `covered()`, `no_hold()` and the `Finding` contract's refusals, each on its own |
| `test_contracts.py` | Contract tests: the shapes the workflow's steps read from the four record functions, for every stand-in record and failure, that each function returns a copy, and a snapshot of what the model is sent (model, instructions line by line, tool schema, case file as parsed JSON) |
| `test_agent_step.py` | Component tests: the interpreter agent with a scripted client. A report ends the run; the agent is offered one tool; invalid arguments are refused and the model told; three invalid reports end with no finding; an answer in text gives none; a call the script didn't allow fails with `UnexpectedModelCall` |
| `test_endings.py` | Workflow tests: Chapter 11's 15 endings; a model error (scripted as `ChatClientException`, the type the real client raises); and a regression test that with the store busy no `Finding` comes back (Chapter 11's raise passes it, as long as the model wasn't called), scripted with `BUSY_STORE_FINDING` |
| `test_recorded.py` | Integration tests: the case set through the real chat client, with each model reply replayed from a cassette in `cassettes/test_recorded/`, asserting the outcome approved when it was recorded (`__snapshots__/test_recorded/`) |
| `test_live.py` | End-to-end tests, marked `live`: the case set against the real model, asserting one designed ending within the agent's call limit |
| `cases.json`, `case_set.py` | The case set (six shipments and their known answers) and `misses()`, which compares an output's typed fields with a known answer |
| `run_cases.py` | Runs the case set against the real model several times per case and prints each output and a score per case |
| `replay_mismatch.py` | No model. A recorded reply replayed with the agent's instructions as recorded, then with one phrase changed |

## The change, by hand and by the suite

```bash
uv run python ch12/workflow.py --with-change
uv run python ch12/workflow.py SH-5120 --with-change
uv run python ch12/count_runs.py 5 ch12/workflow.py --store-busy --with-change
uv run pytest ch12 --with-change -q --tb=short
```

With the change, both hand checks pass: SH-4471 gives the supported refiling of DOC-5531 against RTM-88213 (one model call), and SH-5120 gives `nothing_wrong` with no model call. With the store busy, 2 of 5 runs returned a `cause_found` finding that passed the workflow's check and said the commercial invoice "has not been received" (it's on file, filed against the wrong case); 3 of 5 were flagged `undetermined`. An earlier batch of five gave the same split. Without the change, `workflow.py --store-busy` stops with `StoreUnavailable` and no model call. The suite on the changed workflow: 1 failed (`test_no_finding_from_failed_searches`, "AssertionError: a finding from failed searches"), 65 passed. Chapter 11's own `test_endings.py`, run on a copy of Chapter 11's code with the same change, failed its busy-store test with `IndexError: pop from empty list` from the old scripted client.

## The deterministic suite

```bash
uv run pytest ch12 -v
```

66 passed and 6 deselected (the live tests) in about a quarter of a second, with 7 snapshots: 13 unit tests, 24 contract tests, 6 component tests, 17 workflow tests and 6 recorded tests. Replaying needs no network and no valid API key, though `DEEPSEEK_API_KEY` must be set to something, because the shared client reads it at import.

To see which tests catch a change to the instructions, we changed "would fix it." to "would fix it, in one sentence." in `steps.py`, ran `uv run pytest ch12 -q --tb=line`, and restored the file: 5 failed, 61 passed. The snapshot of what the model is sent failed, with a diff showing the one changed line, and so did the four recorded cases that reach the agent, each because no recorded request matched. Changing RTM-88301's hold reason in `cobalt.py` to "required document missing" for one run failed 2 tests: the contract test for that case (the reason is outside the known vocabulary) and SH-4502's recorded test (the case now ends `outside_procedure` before the agent step). `replay_mismatch.py` shows the same mismatch in one program: SH-4471's recording replays as `cause_found`, and with one phrase changed the run fails with the framework's `ChatClientException`, caused by vcrpy's `CannotOverwriteExistingCassetteException`.

To re-record after a deliberate change (one model call per case that reaches the agent), then review the new outcomes before committing them:

```bash
uv run pytest ch12 --record-mode=rewrite --snapshot-update
```

## The case set and the live tests

```bash
uv run python ch12/run_cases.py 5
uv run pytest ch12 -m live -v
```

Known answers matched in two batches of five: SH-4471 10 of 10, SH-4560 10 of 10, SH-4502 5 of 10 (the other five cited `SH-4504`, a record that doesn't exist, and were flagged by the check), SH-4588 0 of 10 (every run reported `nothing_wrong` instead of `undetermined`, and was flagged); SH-5120 and SH-4533 end before the agent step. A batch cost 21 to 23 model calls. The live tests passed 6 of 6 (four model calls, one per case that reaches the agent); an earlier version that asserted one model call per run failed on SH-4588, which made four: three reports refused by the contract, then the framework's last call with tools off.
