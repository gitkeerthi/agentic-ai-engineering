# Chapter 9 Labs: Tool Approval and Human Gates

The investigation agent from Chapter 8, given its first tool that changes a record: `refile_document`, which submits a new filing of a document to customs. The programs show an instruction failing to hold the write back, the framework's approval round-trip (asked in one process, answered in another), what the framework runs when an approval response is altered or sent twice, an approval that has gone stale, a reply lost after the store committed, where an Agent Hooks deny lands for a tool that needs approval, the loop's limits across a long wait, the framework's behavior around approvals checked with a scripted client, and the chapter's refiling gate. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different decision, from the chapter's.

Tested with agent-framework-core 1.24.0, agent-framework-openai 1.18.0 and agent-hooks-sdk 0.1.0b3. The programs write their records, saved sessions and approval queue to `ch09/state/`, which git ignores; each program that starts an investigation resets the records first. `investigate.py` keeps the framework's warnings out of the transcripts, including the "Ignored ... approval response" warning it logs when it ignores a response; each program prints what ran instead.

| File | What it is |
|---|---|
| `cobalt.py` | Chapter 8's records, saved to a file, with a version on each document; the four read tools; the document store's write API `refile()` (its rules in `check_refile()`, a compare-and-set on `expected_version`, an idempotency key, the approver recorded with the filing); `refile_document` (needs approval) and `refile_document_unguarded` (runs when the model asks), made from the same function, which uses the gate's approval ID as its key, and the approver's name, only for the call whose arguments match the approved ones, and retries only with a key; lab switches `reset(note=True)`, `drop_next_reply()`, `colleague_replaces_invoice()` and `COMPARE_VERSIONS` |
| `investigate.py` | Two sets of instructions (`INSTRUCTIONS` tells the model not to refile without approval; `GATED_INSTRUCTIONS` tells it every refiling waits for an analyst), the task, `run_args()`, `investigator()`, `show()`, and helpers that save a pending request and build the answer message |
| `typed_note.py` | The agent with `refile_document_unguarded` and an uploader's note on DOC-5531 claiming approval. `--no-note` runs it without the note |
| `approval.py` | The same note, with `refile_document` needing approval. The run ends with an approval request; the program saves the session and the request. `--old-instructions` uses `INSTRUCTIONS` |
| `decide.py` | Answers a saved request in a new process: `decide.py <request-id> --approve` or `--reject` |
| `tampered.py` | Answers a saved request with a response altered to name DOC-5532, then sends the same response again |
| `stale.py` | A colleague replaces the invoice while the request waits, then the analyst approves. `--no-version-check` makes the store ignore `expected_version` |
| `lost_reply.py` | No model call. A scripted client asks for the refiling, the program approves it, the store files and its reply is lost. By default the approval carries the gate's runtime values, so the tool retries with a key; `--no-key` approves without them, as `decide.py` does, so the tool tries once; `--retry-without-key` calls the retry wrapper with no key, as a tool that retried anyway would; `--no-version-check` |
| `hook_order.py` | An Agent Hooks interceptor that denies every refiling, on a tool that needs approval: when is the analyst asked, and when does the hook run? |
| `long_wait.py` | `max_duration_seconds=30` and an approval 35 seconds later. `--harness` adds the framework's `ToolApprovalMiddleware` |
| `gate.py` | The refiling gate: `submit()` accepts one approval request per run, refuses what the store would refuse, and queues the rest; `refusal()` checks who may answer and whether the request is still open; `expire_due()` closes pending requests whose lifetime has passed; `decide()` records the decision in a field of its own, sends it (on an approval, with the approval's ID, the approver and the approved arguments validated against the tool's schema), reads the outcome from the store (filed, not filed, unknown after a failed run, or unclear when the store has nothing under the key but the tool reports a filing), and sends any request the agent makes afterwards back through `submit()`, which queues a new call and refuses one the queue already holds, so a rejected or expired request isn't put to anyone again; `recover()` settles an unknown outcome by asking the store and resending the recorded decision only if nothing was filed, and refuses an unclear one, which a person checks; `close()` answers a request no person will decide. `facts()` shows the reviewer the record as it is now, including whether it changed since the agent read it |
| `refiling_gate.py` | The gate as commands: `ask` (`--lifetime` seconds), `review`, `colleague` (lab: a colleague replaces the invoice), `decide <request-id> --by <user> --approve` or `--reject` (`--crash` dies after recording the decision), `recover <request-id>`, `status`. `review` and `decide` run the expiry sweep first |
| `gate_checks.py` | No model call. The store's rules on three proposed refilings; the gate's response to five answers to queued requests; the gate's endings with the scripted client: a request the store's rules refuse, closed before review, a rejection whose send fails, an approval whose run fails after the tool ran, a conflict that makes the agent ask again with a new version, a rejection after which the agent asks for the same refiling (refused) and a fresh investigation that asks for it afterwards (queued), and the expiry sweep, after which the agent asks again (refused); and three checks of how the gate keys an approved call: a version the model sends as text, a reply that asks for two refilings, and a refiling that `ToolApprovalMiddleware` approves automatically in a run the gate resumed. It resets the records and the queue |
| `middleware_and_approval.py` | A function middleware that prints every call it wraps, on a tool that needs approval. `--reject`; `--rewrite` changes the approved arguments |
| `scripted.py`, `scripted_checks.py` | No model call. A lab-only client that replies from a script, and six checks of the framework around an approval: two tools in one reply, a response (as approved, and altered) sent back without a session, what the model is sent on resume, the loop's iteration and call limits across the round-trip, the session after a failed resume, and two refilings in one reply decided one at a time |
| `count_runs.py` | Runs a program several times and counts the outcomes it reports |

## An instruction, and a note that says approval was given

```bash
uv run python ch09/typed_note.py
uv run python ch09/count_runs.py 10 ch09/typed_note.py
uv run python ch09/count_runs.py 10 ch09/typed_note.py --no-note
```

With the note on DOC-5531's record, 2 of 10 runs refiled without anyone approving, and both answers said the refiling was done. Without the note, 0 of 10.

## The approval round-trip

```bash
uv run python ch09/approval.py
uv run python ch09/decide.py <request-id> --approve    # the ID approval.py printed
uv run python ch09/approval.py
uv run python ch09/decide.py <request-id> --reject
uv run python ch09/count_runs.py 10 ch09/approval.py
uv run python ch09/count_runs.py 10 ch09/approval.py --old-instructions
```

The run ended with one approval request and DOC-5531 unchanged; the run's last text said "I'll refile it against RTM-88213." `decide.py`, run afterwards in a new process, loaded the saved session; on approval the framework ran the stored call (filing FIL-001), and on rejection the model read "Error: Tool call invocation was rejected by user." and recommended the refiling again. With `GATED_INSTRUCTIONS`, 10 of 10 runs asked for approval, and in 3 of them (runs 4, 7 and 9) the text beside the request repeated the note's claim of a prior approval; with the old instructions, 1 of 10 asked. Nothing was refiled before approval in any of the 20.

## What the framework runs

```bash
uv run python ch09/approval.py
uv run python ch09/tampered.py <request-id>
```

The response came back naming DOC-5532; the framework ran the call it had stored, refiling DOC-5531, and DOC-5532 stayed unfiled. The same response sent again ran nothing. Both times the model's answer described the completed refiling as awaiting approval.

## An approval that has gone stale

```bash
uv run python ch09/stale.py --no-version-check
uv run python ch09/stale.py
```

Without the version check, the store filed the replaced invoice too: RTM-88213 ended with two commercial invoices, DOC-5540 and DOC-5531. With it, the store answered "conflict" and filed nothing; the model looked again, found DOC-5531 marked as replaced, and recommended that the analyst confirm DOC-5540.

## A lost reply

```bash
uv run python ch09/lost_reply.py
uv run python ch09/lost_reply.py --no-key
uv run python ch09/lost_reply.py --retry-without-key
uv run python ch09/lost_reply.py --retry-without-key --no-version-check
```

With the key, the tool retried: one filing and the true answer. Without the key, the tool tried once: one filing, and the model got "Error: Function failed.", so the outcome was unknown. A caller that retried without a key got a false "conflict" with one filing, and, without the version check, made two filings at customs.

## Where an Agent Hooks deny lands

```bash
uv run python ch09/hook_order.py
```

The run returned an approval request first. The hook's `pre_tool_call` ran only after the analyst approved, and blocked the call then.

## The time limit and a long wait

```bash
uv run python ch09/long_wait.py
uv run python ch09/long_wait.py --harness
```

Without the harness, the resumed run had a fresh time budget and the approved call ran 40 seconds after the first run started. With `ToolApprovalMiddleware`, the budget included the wait: the framework did not run the approved call, and the next model request, which still held the unanswered tool call, was rejected by the provider with a 400 error. `scripted_checks.py` (checks 4 and 5) shows the iteration and call limits behave the same way, and that after the failure the pending request is gone and a second attempt fails too.

## What function middleware sees, and the framework checked without a model

```bash
uv run python ch09/middleware_and_approval.py
uv run python ch09/middleware_and_approval.py --reject
uv run python ch09/middleware_and_approval.py --rewrite
uv run python ch09/scripted_checks.py
```

The middleware saw the four reads as they ran, the refiling only on the approved run, and nothing of a rejected one. With `--rewrite`, the framework didn't run the changed call; it returned a replacement approval request with the reason "Function arguments changed after approval." The scripted checks: with a session, a reply asking for both tools surfaces only the refiling for approval and holds the lookup; without one, it asks about both. Without a session, a response sent back runs nothing, whether as approved or altered to name DOC-5532. Text sent with a decision reaches the model between the tool call and its result. When one reply asks for two refilings, the framework runs neither until both have a decision, then runs both in the run that carries the second.

## The refiling gate

```bash
uv run python ch09/refiling_gate.py ask
uv run python ch09/refiling_gate.py review
uv run python ch09/refiling_gate.py decide <request-id> --by lead-031 --approve
uv run python ch09/refiling_gate.py decide <request-id> --by lead-044 --approve
uv run python ch09/refiling_gate.py ask
uv run python ch09/refiling_gate.py decide <request-id> --by lead-031 --reject
uv run python ch09/refiling_gate.py ask --lifetime 5      # then decide after 5 seconds
uv run python ch09/refiling_gate.py ask
uv run python ch09/refiling_gate.py colleague
uv run python ch09/refiling_gate.py review
uv run python ch09/refiling_gate.py ask
uv run python ch09/refiling_gate.py decide <request-id> --by lead-031 --approve --crash
uv run python ch09/refiling_gate.py status
uv run python ch09/refiling_gate.py recover <request-id>
uv run python ch09/gate_checks.py
```

The review showed what approving does, how long the request had waited, the store's facts read at review time, and, apart from them, the model's reasoning. lead-031's approval filed FIL-001; the tool's result named the approver, the model reported the refiling as done, and the gate recorded "filed" with the store's answer. lead-044's second approval was turned away because the request was no longer pending. A rejection reached the model as the framework's fixed text and the queue recorded "rejected", nothing filed. An expired request was closed by the sweep at the start of `decide`, before the lead's approval was looked at, so the approval was turned away. After `colleague`, the review screen showed DOC-5531 at version 2, replaced by DOC-5540. `gate_checks.py`'s endings: a rejection whose send failed was recovered as a rejection with nothing filed; an approval whose run failed after the tool ran was recovered without a second filing; with a gate swapped in that compares the model's raw text, an approved call sent with the version as `"1"` was filed without its key, the queue recorded "unclear", and `recover` refused it; a conflict left the first request "not filed" and the agent's new request, with version 2, pending; after a rejection, the agent's request for the same refiling was recorded "refused" as a repeat of the rejected request, while a fresh investigation's identical request was queued; the sweep closed an expired request, and the agent's repeat was refused too. A request to refile against SH-4398's case was recorded "refused" and never queued; the model was sent the rejection, then the reason in a message of its own. With the version sent as `"1"`, the approved refiling was still filed under its key with lead-031's name. A reply asking for two refilings was refused by `submit()`. With an automatic approval rule for DOC-5532, both refilings were filed in the resumed run, and only DOC-5531's carried lead-031's name. With `--crash`, the queue was left at "approved" with nothing filed; `recover` found no record at the store, resent the same decision with the same key, and the request ended "filed"; a second `recover` refused. `gate_checks.py` shows each rule: a destination case that belongs to another shipment, an unknown document, an approver who isn't on the list, an approver who asked for the refiling, an expired request, and one already answered.
