# Chapter 6 Labs: State and Context Engineering

The investigation agent from Chapter 5, with its tools behaving normally, asked more than one question. The programs show what the agent forgets between runs, what a session keeps, how a session survives a restart or a failed run, what one model call contains and how it grows, and what each of the framework's main compaction strategies keeps and loses. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different conclusion, from the chapter's.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0. Microsoft marks compaction as experimental in Python, though the framework doesn't warn when it's used.

| File | What it is |
|---|---|
| `cobalt.py` | Chapter 5's records and the four tools in their final form (placeholders in the descriptions, written results when nothing is found, a free-text document type), with no failure switches |
| `investigate.py` | The instructions, the four questions the programs ask, `investigator(**settings)` to build the agent with extra settings such as a compaction strategy, `show(result)`, and `meter`, a chat middleware that records each model call's input and cached tokens |
| `forgets.py` | Two runs with no session: the investigation, then a follow-up |
| `session.py` | The same two runs in one session, then what the session holds |
| `save_session.py` | `save` investigates and writes the session to `saved-session.json`; `resume`, in a new process, reads it back and asks the follow-up |
| `failed_run.py` | The fourth model call fails. What the session keeps with the default saving, with `--per-call` (saving after every model call), and with `--per-call --repair` |
| `context_parts.py` | The tokens each part of one model call costs: task, instructions, tool definitions, history |
| `conversation.py` | Three questions in one session, with every model call's input and cached tokens. Saves the session to `conversation.json` for `compaction.py` |
| `long_results.py` | A fifth tool, `read_document`, that returns a document's full text (stand-in texts of SH-4471's invoice and packing list). A check that reads both, then the follow-up, with the token counts of every call; `--compact` collapses old tool results at the start of each run |
| `compaction.py` | One compaction strategy (`--strategy`) applied to the saved conversation, then a question about its start. Prints what the first model call was sent |
| `cache_cost.py` | The same four questions with no compaction, with truncation before every model call, or with truncation of the stored history after each run, and what each costs once the provider's cache is counted |
| `window_in_run.py` | A sliding window smaller than one investigation: which model calls still include the task |
| `middleware_view.py` | Canned replies in place of the model: what a chat middleware sees against what a strategy keeps, and which exclusion marks a run saves. No model call |
| `findings.py` | The program keeps each investigation's findings in the session and sends them with every run as extra instructions |
| `count_runs.py` | Runs any of the programs several times and prints a line per run for its last question |

`saved-session.json` and `conversation.json` are written by the programs and ignored by git. They hold every tool result in plain JSON, as a real saved session would.

## Without and with a session

```bash
uv run python ch06/forgets.py
uv run python ch06/session.py
```

In five runs of `forgets.py`, the follow-up was never answered. Two runs looked up the invented ID SH-0000 and gave up, two asked for a shipment ID, and one tried twelve invented IDs. In five runs of `session.py`, every follow-up was answered from the history with one model call and no tool call. The session holds the questions, the answers, every tool request and every tool result. It doesn't hold the instructions or the tool definitions: those come from the agent on every call.

## Keeping a session across a restart

```bash
uv run python ch06/save_session.py save
uv run python ch06/save_session.py resume
```

`resume` builds a new agent with the same instructions and tools, restores the session with `AgentSession.from_dict`, and answers the follow-up in one model call. Restore a session only with the agent configuration that created it, and only for the user it belongs to.

## When a run fails midway

```bash
uv run python ch06/failed_run.py
uv run python ch06/failed_run.py --per-call
uv run python ch06/failed_run.py --per-call --repair
```

A chat middleware makes the fourth model call fail, as a dropped connection would. With the default, the history is saved once, after the run, so the session holds nothing and the rerun repeats every lookup. With `require_per_service_call_history_persistence=True`, the history is saved after every successful model call. The session then ends with a tool request whose result was never saved, and the provider rejects the next run with a 400 error. `--repair` drops that unanswered request first; the rerun then continues from the last saved result. A separate check that failed the call at the OpenAI library's request call, beneath every middleware, left the same history.

## What a call contains, and how it grows

```bash
uv run python ch06/context_parts.py
uv run python ch06/conversation.py
```

`context_parts.py` sends the same follow-up four times, adding one part each time, and reads the provider's input count for the first model call of each run. One run measured the task at 20 tokens, the instructions at 148, the four tool definitions at 669 and a 12-message history at 854. `conversation.py` showed input growing from 836 tokens on the first model call to 2,275 on the tenth, with 12,800 of the 14,494 input tokens read from the provider's cache.

## When compaction earns its place

```bash
uv run python ch06/long_results.py
uv run python ch06/long_results.py --compact
```

`long_results.py` asks the agent to check that SH-4471's commercial invoice and packing list list the same items in the same quantities, then asks the chapter's follow-up in the same session. The two documents are stand-in texts of 4,676 and 4,340 characters. In one run, they added about 3,100 tokens to the request at once, and the follow-up, answered from the history in one call, carried 5,217 input tokens, against 1,691 after a plain investigation. With `--compact`, a `CompactionProvider` with `ToolResultCompactionStrategy(keep_last_tool_call_groups=0)` as its before-run strategy collapsed the check's four tool-call groups before the follow-up. The two documents, read in one reply, became one message of 4,096 characters, the strategy's cap. The follow-up carried 3,094 tokens but found only 896 of them in the provider's cache, so its input cost 2,216 uncached-token units against 325 without the collapse. Both runs answered the follow-up correctly. The program prints those costs with cached input priced at a fiftieth of uncached input.

## Compaction

```bash
uv run python ch06/conversation.py                                  # writes conversation.json
uv run python ch06/compaction.py --strategy none
uv run python ch06/compaction.py --strategy sliding-window
uv run python ch06/compaction.py --strategy truncation
uv run python ch06/compaction.py --strategy tool-results
uv run python ch06/compaction.py --strategy drop-tool-calls
uv run python ch06/compaction.py --strategy summary
uv run python ch06/compaction.py --strategy budget
uv run python ch06/count_runs.py 5 ch06/compaction.py --strategy sliding-window
```

Each run loads the same saved conversation (an SH-4471 investigation, a follow-up, an SH-5120 check) and asks which customs case the first shipment's invoice was filed against. The answer is RTM-88124. The limits in `compaction.py` are far smaller than a real agent would use, so each strategy has something to remove from a short conversation. The strategy is set on the agent and runs before every model call. It never deletes stored messages, and the messages loaded from the saved conversation come through unmarked. Only the tool requests, results and answers the current run's loop creates can be saved with an exclusion mark (the run's own question is not), and a strategy in a later run starts from those marks. A chat middleware such as `meter` sees the history before the strategy runs, so it counts the uncompacted list. The chat client adds the instructions after compaction, so no strategy sees or drops them. `compaction.py` wraps the strategy to record what it left in each call; that wrapper is a lab instrument, not something production code needs.

In five runs of each, on the conversation saved for the chapter:

| Strategy | Sent | Correct | Notes |
|---|---|---|---|
| none | 21 messages, 2,495 tokens | 5 of 5 | |
| sliding-window (last 5 groups) | 7 messages, 1,488 tokens | 4 of 5 | one run answered about SH-5120; four looked SH-4471 up again, which they could identify only because a later answer mentioned it |
| truncation | 9 messages, 1,658 tokens | 5 of 5 | the follow-up's answer, which repeats the case, survived |
| tool-results | 15 messages, 2,099 tokens | 5 of 5 | old tool results collapsed into one-line messages |
| drop-tool-calls | 9 messages, 1,800 tokens | 5 of 5 | the answers carried the facts |
| summary | 5 messages, about 1,550 to 1,600 tokens | 5 of 5 | one or two extra model calls to write the summary |
| budget | 15 messages, 2,099 tokens | 5 of 5 | stopped after collapsing tool results |

The token budgets are counted by `CharacterEstimatorTokenizer`, about four characters a token of the serialized messages. It put the saved history at 2,614 tokens; the provider counts about 1,660 for the same messages.

```bash
uv run python ch06/cache_cost.py --mode none
uv run python ch06/cache_cost.py --mode every-call
uv run python ch06/cache_cost.py --mode stored
```

`cache_cost.py` counts what compaction costs once cached input is priced at a fiftieth of uncached input. In one run each: no compaction sent 17,257 input tokens (2,455 in uncached-token units); truncation before every call sent 11,929 and cost 2,897, because every trimmed call started from a history the cache hadn't seen; truncation of the stored history (a `CompactionProvider` with an after-run strategy, and `InMemoryHistoryProvider(skip_excluded=True)`) cut after the third question and again after the fourth, and cost 2,862, all of the extra on the one call after the first cut (the second came after the last call). All three answered the last question correctly. The thresholds are tiny so that a cut happens in four questions; whether and when the stored version cuts depends on how long the answers are.

```bash
uv run python ch06/window_in_run.py
```

With a window of three groups, the task fell out of the model's context from the fourth model call on, in every one of five runs. All five still found the cause, because each step of this investigation needs only the last result.

```bash
uv run python ch06/middleware_view.py
```

`middleware_view.py` replaces the model with canned replies at the OpenAI library, so it makes no model call and costs nothing. It loads `conversation.json`, so run `conversation.py` first. On the go-back question with the five-group window, `meter` saw 21 messages and the strategy kept 7. In a scripted investigation with a three-group window, the task dropped out from the fourth call on; afterward the stored task carried no exclusion mark, while the first tool request and its result did. In a second run on the same session, the program prints each count with what it includes: with no strategy, the 10 loaded messages and the new question reached the middleware, the marks were ignored, and the provider request carried those 11 plus the instructions; with a 100-group window, the strategy left out the 2 marked messages.

## Findings kept outside the history

```bash
uv run python ch06/findings.py
```

After each investigation, the program reads the answer's Cause and Recommended action lines and the IDs it mentions, and keeps them in `session.state["findings"]`. Every later run sends them as extra instructions, which the framework adds to the agent's own and which compaction never removes. With the same five-group window, five of five runs named SH-4471 as the first shipment and answered RTM-88124. Each confirmed the fact with a lookup first: one lookup in four runs, three in the fifth. Reading the findings from the answer's text works only while the answer keeps its format; Chapter 10's structured output makes it reliable. The note copies the model's own Cause and Recommended action sentences into the instructions, which suits a demonstration on our own records. In production, build it from fields the program has checked, because whatever goes in the instructions carries their authority.
