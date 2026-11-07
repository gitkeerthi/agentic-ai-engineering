# Chapter 14 Labs: Observing Runs and Measuring Cost

Chapter 13's investigation workflow, observed: each traced run leaves a trace (OpenTelemetry, through Microsoft Agent Framework's instrumentation plus spans of our own), a case record carrying the trace ID, an evidence record of what the agent was sent and replied, log lines and metrics. Programs here reconstruct a run from its trace ID, replay its recorded request while checking which dependencies still match, and measure tokens, latency and cost per run, per case and per successful run. Run the programs from `code/volume-1/`, the folder above this one. Model replies vary from run to run, so live runs may give different counts from the chapter's.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0, on DeepSeek's `deepseek-flash` with thinking disabled; the larger model is `deepseek-v4-pro`. Four dependencies were added for this chapter, and `uv sync` installs them: `opentelemetry-instrumentation-logging` (its `LoggingHandler` replaces the SDK's deprecated one), `opentelemetry-exporter-otlp-proto-http` (Langfuse takes OTLP over HTTP, not gRPC), `opentelemetry-processor-baggage` (copies baggage onto spans), and `langfuse`, Langfuse's Python SDK, used only as a client for its API. Langfuse itself, 4.72.0, runs in Docker.

## Files

| File | What it is |
|---|---|
| `cobalt.py`, `contracts.py`, `versions.py`, `golden.json` | Chapter 13's, unchanged |
| `scripted.py` | Chapter 13's scripted client, with the framework's telemetry layer added so its calls get `chat` spans |
| `steps.py` | Chapter 13's workflow steps; every read of Cobalt's records goes through `telemetry.read()`, which gives it a span |
| `golden.py` | The golden set's known answers, and `right()`, which compares a saved output with them |
| `telemetry.py` | Not a program. The OpenTelemetry setup (service name and release, sensitive data off, spans, logs, and metrics exported to `store/NAME/`), the seven-part configuration a run records, `read()`, the correlation ID (the trace ID, or an ID of its own when tracing isn't set up), the evidence middleware, `investigate()` (the root span, the business metric, the case record). Our spans and metric use the instrumentation scope `cobalt.investigation` |
| `show.py` | Not a program. Reading the stores back, and printing a trace as a tree |
| `observed.py` | One observed investigation; prints the case record and the trace read back from the trace store |
| `week.py` | The observed investigation on every golden case, several runs each: a stand-in for a week of production runs |
| `reconstruct.py` | No model. A run rebuilt from its trace ID: case record, configuration compared with `evaluated.json`, trace, time, tokens and cost; `--evidence` adds what the agent was sent and every report it made |
| `evaluated.json` | The configurations Chapter 13 evaluated (instructions hash, model, framework version), copied from its saved runs |
| `replay.py` | A recorded request sent again N times; takes a trace ID or a Chapter 13 run (`ch13:VERSION:SHIPMENT:RUN`). Restores instructions and case file, compares recorded tools, code, client settings, model, and framework with today's, and reports missing historical values as `not recorded` |
| `costs.py` | No model. Tokens, latency and cost (list prices) per run, per case and per success, for stores or for Chapter 13's saved runs (`--ch13 A B`) |
| `metrics.py` | No model. The last metrics export of a store |
| `refusals.py` | No model. Every report the framework refused in a store's evidence, sorted into not JSON and refused by the contract |
| `what_a_trace_holds.py` | No model. Each span's attributes with sensitive data off or on (`--sensitive`), and where the run's content appears |
| `context_spans.py` | No model. What a context provider and a history provider leave in a trace, without and with spans of our own (`--span`) |
| `propagate.py`, `reviewer.py` | No model. A flagged case put on a review queue with its trace context and taken off by a second process in the same trace |
| `conftest.py`, `test_telemetry.py` | Model-free tests of what every run must leave behind |
| `to_langfuse.py` | Not a program. The OTLP span exporter to Langfuse, which adds each model call's cost as `gen_ai.usage.cost`, and the contrib `BaggageSpanProcessor` that copies the run's shipment, carried as baggage, onto every span as `session.id`. Used by `telemetry.setup(..., langfuse=True)` |
| `langfuse/compose.yml`, `langfuse/new_env.py` | Langfuse's own Docker Compose file (tag v4.72.0, with the two Langfuse images pinned to 4.72.0; ClickHouse 25.12, Redis 7, PostgreSQL 17 and MinIO's untagged image as upstream has them), and the program that writes its `.env`: a random value for every secret, and the project, keys and user Langfuse creates on first start |
| `scores.py` | No model. Each run's result against the golden set, attached to its trace in Langfuse as a categorical score |
| `in_langfuse.py` | No model. What Langfuse holds for a store's runs, read back through its API: one run's observations, cost and latency by model, scores, sessions, traces by root, tokens by observation type, beside the root spans' totals |
| `store/` | The saved stores the chapter reads (below) |

## What `store/` holds

Each store is a folder of JSON Lines files: `spans.jsonl` (one span per line, the OpenTelemetry SDK's JSON), `logs.jsonl`, `metrics.jsonl` (one export per line, cumulative), `cases.jsonl` (the case system's record of each run, with its trace ID) and `evidence.jsonl` (what the agent was sent and its whole response, keyed by the trace ID). Programs append; delete a store's folder to start it fresh.

| Store | Written by | What it holds |
|---|---|---|
| `week` | `week.py week --runs 10` | Version A on the lab model: 93 runs, 100 model calls |
| `larger` | `week.py larger --model larger --runs 5` | Version A on the larger model: 48 runs, 45 model calls |
| `observed` | `observed.py` | One run on SH-4471 |
| `holds-off`, `holds-on` | `what_a_trace_holds.py [--sensitive]` | One scripted run each |
| `context`, `context-span` | `context_spans.py [--span]` | Two scripted runs each |
| `propagate` | `propagate.py` and `reviewer.py` | One scripted run, and the reviewer's span |
| `langfuse` | `week.py langfuse --runs 3 --langfuse` | Version A on the lab model, also sent to Langfuse: 30 runs, 34 model calls |
| `langfuse-larger` | `week.py langfuse-larger --model larger --runs 2 --langfuse` | Version A on the larger model, also sent to Langfuse: 21 runs, 18 model calls |

The tests write to `store/tests/`, which is rebuilt on every run and not kept.

## One run, observed (Examples 14-3 and 14-4)

```bash
uv run python ch14/observed.py
```

One model call. The trace has 26 spans on SH-4471 (the printout leaves out `workflow.build` and the five `edge_group.process` spans): our root span, the workflow's run, each step's `executor.process` span, our spans for each read, the `message.send` span for each message between steps, and the agent's `invoke_agent`, `chat` and `execute_tool` spans. Every read takes no measurable time (the records are in memory), so the run's time is the model call's.

Sending the same spans to Jaeger instead of, or as well as, the files takes the standard variable (Chapter 4's README starts Jaeger):

```bash
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4317 uv run python ch14/observed.py
```

## Context providers and memory in the trace (Example 14-5)

```bash
uv run python ch14/context_spans.py
uv run python ch14/context_spans.py --span
```

No model. Without our spans, the trace shows only `invoke_agent` and `chat`: the providers' work is invisible. With them, `memory load`, `context current_status` and `memory save` spans appear inside `invoke_agent`, recording counts and record IDs.

## The observed batch and its reconstructions (Examples 14-6, 14-9, 14-15 to 14-17)

```bash
uv run python ch14/week.py week --runs 10
uv run python ch14/reconstruct.py cbde22a3857abc64494c2ed7d6018fa6 --evidence
uv run python ch14/reconstruct.py a1f1c952d5ca68523883f18b95b9df12 --evidence
uv run python ch14/refusals.py week
```

`week.py` makes about 100 model calls (about two and a half cents at off-peak prices, five at peak). Our batch released 65 findings, two of them wrong, both disguised abstentions (a `cause_found` whose cause says the records don't explain the hold) on SH-4588 (`cbde22a3857abc64494c2ed7d6018fa6`, `5947d8ab29ed7e37842d6c1a038f1593`). The second reconstruction is an SH-4656 run with four model calls and no tool span: three reports refused (one not JSON, two with `undetermined` and the string `"null"` as a cause, which the contract refuses), then the framework's tools-off call at its limit of three consecutive errors, and a flagged case, though the model's `undetermined` was the known answer. `refusals.py` finds 10 refused reports in 6 of the batch's 90 agent runs: 6 not JSON, 4 refused by the contract. `reconstruct.py` and `refusals.py` read the saved stores and make no model call; running `week.py` again appends a new batch to the store.

## Replaying the recorded request (Example 14-18)

```bash
uv run python ch14/replay.py ch13:A:SH-4656:9 20
uv run python ch14/replay.py cbde22a3857abc64494c2ed7d6018fa6 20
```

About 30 model calls each, counting retries. Each first compares the recorded configuration with today's: Chapter 13's run recorded the model and framework (both the same) and not the tools, code, or client; the batch's run matches today's on every recorded part. Chapter 13's released wrong finding's captured input: `cause_found` 3 of 20 (two disguised abstentions, one that invents a filing defect the case file doesn't contain), `nothing_wrong` 9, `undetermined` 6, no valid report 2. The batch's SH-4588 recorded request: no `cause_found` in 20 (`nothing_wrong` 17, `undetermined` 3), though two of the batch's ten SH-4588 runs made that mistake.

## One trace across two processes (Examples 14-11 and 14-12)

```bash
uv run python ch14/propagate.py
```

No model. The queued message's headers carry a `traceparent`, and the reviewer's span, recorded by a second process under the service name `cobalt-review`, sits under the span that queued the case.

## Tokens, latency and cost (Examples 14-19 to 14-21, Tables 14-4 and 14-5)

```bash
uv run python ch14/costs.py week larger
uv run python ch14/costs.py --ch13 A B
uv run python ch14/metrics.py week
```

No model; list (peak) prices. The observed batch: $0.00052 per run, median 1.97 s and slowest 7.76 s for runs that reached the model, 99.6% of the time in model calls; by number of model calls, 84 one-call runs (median 1.94 s), 4 two-call (3.45 s), 2 four-call (7.61 s); $0.00074 per released finding and $0.00076 per released finding that was right. The larger model: $0.00123 per run, median 3.93 s, no retries, 37 releases, none wrong, $0.00160 per right release. Chapter 13's saved runs: version A $0.00076 and version B $0.00091 per right release. The framework's metrics (`gen_ai.client.token.usage`, `gen_ai.client.operation.duration`, `agent_framework.function.invocation.duration`) don't split cached from fresh input, so cost comes from the spans. Each metrics export carries exemplars only from its own interval.

## What the trace holds (Examples 14-14 and 14-22)

```bash
uv run python ch14/what_a_trace_holds.py
uv run python ch14/what_a_trace_holds.py --sensitive
```

No model. With sensitive data off, no text from the case file, the instructions or the finding appears in any of the 27 spans or in the logs; the evidence store holds the case file. With it on, the `chat`, `invoke_agent` and `execute_tool` spans and three log records hold them.

## Runs in Langfuse (Examples 14-23 to 14-26, Figures 14-6 and 14-7, Table 14-8)

Langfuse runs locally in Docker: six containers (the web server and a worker, PostgreSQL, ClickHouse, Redis, MinIO). Langfuse suggests at least 4 cores and 16 GiB of memory for a machine that runs them.

```bash
uv run python ch14/langfuse/new_env.py          # once: writes ch14/langfuse/.env
docker compose -f ch14/langfuse/compose.yml up -d
uv run python ch14/week.py langfuse --runs 3 --langfuse
uv run python ch14/week.py langfuse-larger --model larger --runs 2 --langfuse
uv run python ch14/scores.py langfuse
uv run python ch14/scores.py langfuse-larger
uv run python ch14/in_langfuse.py langfuse langfuse-larger
```

The two batches cost $0.0202, off-peak (52 model calls). `new_env.py` turns off the Compose file's default `TELEMETRY_ENABLED=true`, which sends usage statistics to Langfuse; the `.env` it writes holds the secrets and is not in the repository. Sign in at `http://localhost:3000` as `analyst@cobalt.example` with the password in `.env`.

What we saw with Langfuse 4.72.0: the framework's `chat`, `invoke_agent` and `execute_tool` spans became a generation, an agent and a tool, and `service.version` became each observation's version; a generation's usage excludes the cached tokens (153 + 1,152 cached, where `gen_ai.usage.input_tokens` is 1,305), though the metrics API's input-token total adds them back; agent observations carry no usage or cost (Langfuse skips them on `invoke_agent` spans by design), so totals count each model call once; Langfuse's cost, input and output totals for the 51 runs ($0.0202; 68,585; 16,826) equal the root spans'; it holds 102 traces, because `workflow.build` starts a trace of its own before each run's root span; 41 runs scored `right`, 9 `flagged` and 1 `wrong` (the larger model on SH-4588: `uv run python ch14/reconstruct.py 6acff0068a137877d63674c817437748 --store langfuse-larger`); the scores view filtered by session returns no trace scores. The worker logs errors from Langfuse's in-app agent feature and a background migration on startup; ingestion, scores and queries worked regardless.

To see a run in Langfuse's own view (Figure 14-7 is the wrong SH-4588 run), open `http://localhost:3000/project/investigation/traces/TRACE_ID` with a trace ID from a case record or from `in_langfuse.py`'s list of `wrong` verdicts.

To start again from nothing: `docker compose -f ch14/langfuse/compose.yml down -v`, then delete `ch14/langfuse/.env`.

## Tests

```bash
uv run pytest ch14
```

Nine model-free tests: the root span carries the configuration; the case record's trace ID finds the model and tool spans; the evidence is kept under the same ID, including when the model call fails; no case-file or finding text reaches the trace or logs; a run that fails on a busy document store still leaves a trace (root and read spans marked `ERROR`) and a `failed` case record; a flagged run logs one line with its trace ID; without tracing, each run still gets an ID of its own; and a read that raises records its error class without its message.

## Experiments beyond the chapter

`uv run python ch14/reconstruct.py 5947d8ab29ed7e37842d6c1a038f1593 --evidence` reconstructs the batch's other wrong finding, also on SH-4588, for free. Its report has the same shape as Example 14-15's: both required documents received and filed, and a `cause_found` whose cause is that the hold reason doesn't match the records.

`uv run python ch14/replay.py ch13:B:SH-4656:2 10` replays one of version B's six wrong findings from Chapter 13 with B's instructions (22 model calls in our run). B reported `cause_found` on that exact request 2 times in 10, with 4 `undetermined` and 4 runs that ended with no valid report: under instructions that forbid `nothing_wrong`, the model's answers on this input split between the honest abstention, the disguised one, and reports the contract refused until the framework stopped calling tools.
