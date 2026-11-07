# Chapter 7 Labs: Context Providers

The investigation agent from Chapter 6, in a session, while Cobalt's records change underneath it. The programs show what the agent says when the history it holds is out of date, the two simple fixes, what the framework does with context providers before and after a run, a provider that puts current records in front of the model, where its note lands and what that does to correctness and the prompt cache, a file-backed history that repairs itself when it loads, and four providers on one agent. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different conclusion, from the chapter's.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0. `FileHistoryProvider` is experimental, so any program that imports `providers.py` prints an `ExperimentalWarning`.

| File | What it is |
|---|---|
| `cobalt.py` | Chapter 6's records and four tools, plus `release_sh4471()` (the team's fix: the invoice refiled, the case cleared, the shipment released), `pick_up_sh4471()` (the carrier collects it) and `reset()` |
| `investigate.py` | The instructions, the questions the programs ask, `investigator(instructions, **settings)` to build the agent with other instructions or extra settings such as context providers, `show(result)`, and `meter`, a chat middleware that records each model call's input and cached tokens |
| `providers.py` | The chapter's context providers: `ShipmentStatus` (current shipment records on every run), `RepairingFileHistory` (the framework's file-backed history, leaving out tool requests that never got a result) and `Findings` (the findings of earlier investigations, as Chapter 6 did by hand) |
| `stale_update.py` | Investigate SH-4471, release it, then ask for a customer update in the same session. `--still-held` asks whether it's still held instead |
| `instructed.py` | The same, with an instruction to look records up again before stating them |
| `by_hand.py` | The same, with the program putting SH-4471's current record in front of the question |
| `pipeline.py` | Two small providers that report when they're called and add a message and an instruction each; a chat middleware prints what the model was sent. No tools |
| `status_provider.py` | The customer update with `ShipmentStatus`. `--after-history` lists the history provider first, so the note comes after the history |
| `cache_position.py` | Three runs while the record changes twice, with the note after the history, before it, or in the instructions (`--place`). Prints each run's first model call (input tokens, cached tokens), then the answers in full |
| `history_provider.py` | `fail`: the investigation with the history saved after every model call, and the fourth call fails. `resume`: a new process loads the same history and runs the task again. `resume --plain` uses the framework's provider without the repair |
| `several_providers.py` | Four providers on one agent: the repairing history, a store-only audit copy that also keeps the other providers' notes, `Findings` and `ShipmentStatus` |
| `per_call_order.py` | Where the records note lands on every model call of a run, with the history saved once per run or, with `--per-call`, after every model call. Watches each request at the client's last step before it's sent |
| `repeated_question.py` | The same question asked twice in one session, and what the framework's history provider stores |
| `replay_check.py` | What the history providers store when messages repeat: a repeated question, the same exchange twice in a row, a resumed task, and a store-only audit copy in three configurations. Uses `scripted.py`, so it calls no model |
| `scripted.py` | A lab-only chat client that replies from a script instead of calling a model |
| `count_runs.py` | Runs any of the programs several times (the chapter's repetitions), prints each repetition in full, then a line per repetition for its last question |

`history/` is written by `history_provider.py` and `several_providers.py` and ignored by git. Its files hold every tool result in plain JSON Lines, as a real stored history would.

## An out-of-date answer, and two simple fixes

```bash
uv run python ch07/stale_update.py
uv run python ch07/stale_update.py --still-held
uv run python ch07/instructed.py
uv run python ch07/by_hand.py
```

`stale_update.py` asks for the customer update after the shipment has been released. The question doesn't say that time has passed, and the history holds the earlier lookups, which said "held". `--still-held` asks a question that does say so. `instructed.py` adds one instruction; `by_hand.py` changes the task instead of the instructions.

## What a context provider does

```bash
uv run python ch07/pipeline.py
uv run python ch07/status_provider.py
uv run python ch07/status_provider.py --after-history
```

`pipeline.py` makes two cheap model calls and shows the order: each provider's `before_run` in the order the providers are listed, the model call, then each `after_run` in reverse order. It also shows where the additions land: provider instructions after the agent's own, and provider messages before the history, because the framework adds its history provider after the ones you list. Nothing a provider adds is saved in the history.

`status_provider.py` runs the customer update with `ShipmentStatus`. Run it with and without `--after-history` and compare the answers.

## Where the note lands

```bash
uv run python ch07/cache_position.py --place after-history
uv run python ch07/cache_position.py --place before-history
uv run python ch07/cache_position.py --place instructions
```

The record changes before runs 2 and 3, so the note does too. The model service caches the longest unchanged start of a request, so the cached count shows how much of each request matched the one before.

## A history that repairs itself

```bash
uv run python ch07/history_provider.py fail
uv run python ch07/history_provider.py resume --plain
uv run python ch07/history_provider.py fail
uv run python ch07/history_provider.py resume
```

Run `fail` before each `resume`: a successful `resume` adds to the stored history. With the history saved after every model call, the framework loads the history before every model call inside the run, not only at its start, so the repair counts a tool result that arrives with the current call as an answer.

## When the history is saved after every model call

```bash
uv run python ch07/per_call_order.py
uv run python ch07/per_call_order.py --per-call
```

With the history saved after every model call, the framework loads the history before each model call from its own middleware, after the other providers' messages, so the records note goes in front of the history on the run's first model call and is missing from the later ones. Middleware we add runs before that loading, so the program watches the request at the client's last step instead.

## A question asked twice

```bash
uv run python ch07/repeated_question.py
```

```bash
uv run python ch07/replay_check.py
```

Before saving, the framework's history providers drop a replay: incoming messages that repeat the stored history in order, or begin with its last messages. When a message has no ID, matching means the same role and content; the model service's replies carry no ID. The check compares sequences, not single messages. When we ran them, `repeated_question.py` stored all six messages, both copies of the question included, because another exchange sits between them. `replay_check.py` replies from a script, so its output is the same every time: the same question asked twice in a row with the same reply is stored once, and with a different reply twice; a resumed run stores the task a second time; and an audit copy without `store_context_from` holds the conversation twice after the third run (18 messages, against 12 with it), while `store_context_from` without `store_context_messages=True` keeps no notes at all.

## Several providers

```bash
uv run python ch07/several_providers.py
```

The audit copy is a second history provider with `load_messages=False`. `store_context_from` names the providers whose notes it keeps, and takes effect only with `store_context_messages=True`. Without `store_context_from`, the audit copy is also offered the conversation the working history loaded, and from the third run on it saves that conversation again, because its own copy, with the notes between the messages, no longer lines up with it.

## Counting runs

```bash
uv run python ch07/count_runs.py 5 ch07/stale_update.py
uv run python ch07/count_runs.py 5 ch07/status_provider.py --after-history
```

Each `======== Run N` banner numbers one repetition of the whole program. The chapter calls these repetitions and keeps "run" for one call to the agent, so the `Run 1:` and `Run 2:` lines inside a repetition are its two runs, one per question.
