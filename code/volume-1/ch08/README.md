# Chapter 8 Labs: Middleware and Agent Hooks

The investigation agent from Chapter 7, with code that runs around every run, every model call and every tool call. The programs show an audit record written inside each tool going missing for a new tool, the three kinds of middleware and their order, one audit middleware with the caller's identity and personal data redacted (and what happens when the audit store is down), a token meter, a report at any loop limit, two ways to end a run early, three ways middleware can stop a run, and the same token budget written with Agent Hooks. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different conclusion, from the chapter's.

Tested with agent-framework-core 1.24.0, agent-framework-openai 1.18.0 and agent-hooks-sdk 0.1.0b3. Agent Hooks is experimental and the SDK is a beta pre-release; `budget_hook.py` hides the experimental warning.

| File | What it is |
|---|---|
| `cobalt.py` | Chapter 7's records and four tools, plus `get_customer_contact` (a stand-in customer system whose contact name, email and phone are personal data), `make_store_busy()` (every document search answers "busy") and `reset()` |
| `investigate.py` | The instructions, the two tasks, `USER_ID` (who the runs are for), `investigator(tools, max_iterations, **settings)`, `show(result)` and `outcome(result)`, which says how a run ended from its flags, its failed or Agent Hooks-blocked tool results and its structure, not its text |
| `audit_store.py` | A stand-in for an append-only audit store: one JSON Lines file in `audit/`, with a `down` switch |
| `middleware.py` | The chapter's middleware: `audit_trail` (with `redact`, `result_data` and `finish`), `limit_report`, `RepeatStop` and `TokenBudget`, and `BudgetGuard`, the token budget as an Agent Hooks interceptor |
| `audit_per_tool.py` | Four tools that each write their own audit record, and a fifth added without one |
| `layers.py` | Agent, chat and function middleware that print when they run, plus one registered for a single run |
| `audit.py` | `audit_trail` on all five tools. `--store-down` makes every audit write fail; `--naive` swaps in a first version that writes after the call and lets the error escape; `--no-user` runs without saying who the run is for |
| `token_meter.py` | Chat middleware that prints each model call's tokens |
| `limit_report.py` | The investigation at a loop limit of 2, in a session. `--report` adds `limit_report`; `--failing-tools` makes every tool call fail, so the run can end at the error limit instead |
| `replaced_output.py` | Agent middleware that replaces a run's reply after the run, and what the session stores. `--hooks` denies the reply with an Agent Hooks interceptor instead |
| `repeat_stop.py` | The document store answers "busy"; `RepeatStop` ends the run on the third identical request |
| `token_budget.py` | `TokenBudget` stops the run before a model call once the run has used its budget (`--budget`, default 3,000) |
| `ways_to_stop.py` | Middleware that stops a run: `--how terminate`, `failure` or `plain` (an ordinary exception); `--layer function` (the default, on every tool call), `chat` (before every model call) or `agent` (before the run) |
| `budget_hook.py` | The token budget as an Agent Hooks interceptor. `--crash` makes the interceptor raise; `--evaluate-only` records verdicts without acting on them |
| `interception_plan.py` | The chapter's plan together: `audit_trail` and `limit_report` on the agent, `TokenBudget` and `RepeatStop` for each run. `--budget`, `--max-iterations`, `--store-busy` and `--store-down` make the controls fire |
| `count_runs.py` | Runs any of the programs several times and prints each run in full |
| `scripted.py` | A chat client that replies from a script instead of calling a model |
| `scripted_checks.py` | Checks with the scripted client, no model call: how `outcome()` reads the failing-tools endings and a tool-point Agent Hooks deny, `audit_trail` when an inner middleware skips the tool, `MiddlewareTermination` without a substitute, and both token budgets with and without reported usage |

`audit/` is written by the audit programs and ignored by git. `scripted_checks.py` writes its audit records to a temporary folder instead, so it leaves the lab's log alone.

## An audit record in every tool

```bash
uv run python ch08/audit_per_tool.py
```

The agent investigates SH-4471 and drafts a customer update, so it looks up the customer's contact. In our run it made six tool calls, and the audit log held five records: none for `get_customer_contact`, the one call that read personal data.

## Three places to intercept

```bash
uv run python ch08/layers.py
```

In our run: agent middleware once, chat middleware four times (one per model call), function middleware four times (one per tool call). The middleware registered on the agent printed before the one registered for the run, so agent-level middleware wraps run-level. When the model asked for two tools in one reply, their function middleware ran interleaved.

## The audit trail, written once

```bash
uv run python ch08/audit.py
uv run python ch08/audit.py --store-down --naive
uv run python ch08/audit.py --store-down
uv run python ch08/audit.py --no-user
```

With the store up, every call got two records (requested, then how it ended), each with the user ID, and the contact's name, email and phone were `[redacted]`. The model's own answer still named the contact: the redaction applies to the audit record, not to what the model writes. With the store down, the naive version let three tool calls run, the contact lookup among them, and wrote nothing; the model was told each call had failed, repeated one that had succeeded, and the framework stopped tool calls after three errors. The recommended version stopped the run before the first tool ran. Without a user ID, it stopped the same way.

## Watching every model call

```bash
uv run python ch08/token_meter.py
uv run python ch08/count_runs.py 5 ch08/limit_report.py
uv run python ch08/count_runs.py 5 ch08/limit_report.py --report
uv run python ch08/count_runs.py 3 ch08/limit_report.py --report --failing-tools
```

The meter's total matched the response's own token count (5,898 in our run). At a loop limit of 2, all five runs without `limit_report` ended in a request for a tool that doesn't exist. With it, all five ended in a report in the answer format, and the program could read `limit_reached`. The reports were readable, not always right: one said the commercial invoice was missing (it is on file, filed against another case), and several said no tool could tell them more when the run had stopped before the lookup that would have. The session stored the task but not the request for a report. With every tool failing, the model sometimes gives up on its own before the framework's limit of three failing rounds; in our three runs, one reached the limit and was flagged, and the other two weren't, since no limit was reached. `limit_report.py` doesn't call `outcome()`; `scripted_checks.py` replays both endings to show how it reads them.

## Stopping a run

```bash
uv run python ch08/repeat_stop.py
uv run python ch08/token_budget.py
uv run python ch08/ways_to_stop.py --how terminate
uv run python ch08/ways_to_stop.py --how failure
uv run python ch08/ways_to_stop.py --how plain
uv run python ch08/ways_to_stop.py --layer chat --how terminate    # also failure, plain
uv run python ch08/ways_to_stop.py --layer agent --how terminate   # also failure, plain
```

`RepeatStop` ended the run on the third `find_document` request, though the model sent the arguments in a different order the second and third time; it compares them sorted. `TokenBudget` stopped after three calls at 3,187 tokens: it checks before each call, so a run can overshoot by one call. With `--how terminate`, the caller got a response whose last message is the tool result "Stopped by policy." and whose `result.text` is the model's opening sentence, and the session kept three messages. With `failure`, the caller got the exception and the session kept nothing. With `plain`, the framework turned the exception into a tool error each time, the model kept trying, and the run went on until the framework's limit of three errors. With `--layer chat`, terminate made the substitute the run's reply and the session stored it as if the model had written it; with `--layer agent`, terminate returned the substitute and the session stored nothing. In both, `failure` and `plain` reached the caller as exceptions. None of the chat or agent runs calls the model.

## What middleware can't hold back

```bash
uv run python ch08/replaced_output.py
uv run python ch08/replaced_output.py --hooks
```

The agent middleware replaced the reply after the run. The caller got "[withheld by policy]"; the session stored the model's reply, "pineapple", which the next run on that session would read back. With `--hooks`, an interceptor denied the reply at the `output` point: the caller got `InterceptionBlocked`, and the session stored nothing.

## Agent Hooks

```bash
uv run python ch08/budget_hook.py
uv run python ch08/budget_hook.py --crash
uv run python ch08/budget_hook.py --evaluate-only
```

The program prints every interception point and its verdict. In our run the fourth `pre_model_call` was denied and the run raised `InterceptionBlocked`. With `--evaluate-only`, three denies were recorded, at three different token counts, and the run carried on to a full answer. With `--crash`, the interceptor's error became a deny (`host_error:interceptor_failed`) at the first tool call and the run halted: Agent Hooks fails closed, where an ordinary exception in function middleware fails open.

## The plan, together

```bash
uv run python ch08/interception_plan.py
uv run python ch08/interception_plan.py --budget 3000
uv run python ch08/interception_plan.py --max-iterations 2
uv run python ch08/interception_plan.py --store-busy
uv run python ch08/interception_plan.py --store-down
uv run python ch08/interception_plan.py --budget 1500 --max-iterations 2
```

Each run prints `outcome(result)` and the audit log, whose records carry the user, a run ID, and the model's call ID. In our runs: an answer, with a requested and a completed record for each call; a stop at the budget, flagged; a report at the loop limit, flagged; a stop on the third identical search, with a `stopped` record giving the reason; `MiddlewareFailure` before any tool ran, with the store down; and, with the budget and the loop limit set to meet, the budget's substitute reply with `limit_reached` still set.

## Checks without a model

```bash
uv run python ch08/scripted_checks.py
```

A scripted client stands in for the model, so the output is the same every time and costs nothing. `outcome()` reads a run in which two lookups failed and the model then answered as `unclear: the model answered after 2 failed tool call(s)`, and a run that reached the error limit as `partial: a loop limit was reached after 3 failed tool call(s)`; the store-busy stop and a plain answer read as `stopped by middleware: ...` and `answer`. A policy deny from an Agent Hooks interceptor at `pre_tool_call` or at `post_tool_call`, after which the model answers, reads as `unclear: the model answered after 1 tool call(s) blocked by Agent Hooks`: the framework puts "Tool call blocked by agent-hooks at ..." in the tool's result and the run doesn't raise. When a middleware inside `audit_trail` skips the tool and sets no result, `finish()` raises an alert and the model gets the empty result, not a tool error. `MiddlewareTermination` with no substitute raises `AttributeError` in chat middleware and makes `agent.run()` return `None` in agent middleware. With every model call reporting 1,100 tokens, both budgets of 2,000 stop the run before its third call; with no usage reported, neither stops it.
