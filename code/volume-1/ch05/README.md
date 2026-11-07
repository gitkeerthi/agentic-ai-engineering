# Chapter 5 Labs: Tools and Failure Recovery

The investigation agent from Chapter 4, with its tools now calling stand-in *systems* that can fail: a shipment tracker, a customs system and a document store. Each program switches one system into one kind of failure, or replaces one tool, and shows what the model receives and what the agent concludes. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different conclusion, from the chapter's.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0.

| File | What it is |
|---|---|
| `cobalt.py` | The records, the three stand-in systems and their switches (`behavior`: `"down"`, `"flaky"` or `"slow"`; `version`, which changes one answer of the customs system and of the document store), one `reset()`, and the four tools as a developer might first write them (`list_required_documents` returns a Pydantic model) |
| `investigate.py` | Chapter 4's instructions, `investigator(tools)` to build the agent for a set of tools, and `show(result)` to print what the model asked for and received |
| `hidden_outage.py` | The store is down and the tool reports the failure as "not on file" |
| `raised_error.py` | The store is down and the tool lets the error reach the framework |
| `written_error.py` | The store is down and the tool writes an error for the model |
| `retries.py` | The tool retries the store through a tenacity retry policy, with backoff and jitter, and the program counts the calls each layer made |
| `instructed_retry.py` | The store is down, and a line in the agent's instructions, not the tool's result, says not to call a failed tool again |
| `slow_store.py` | The store takes 20 seconds; three different time limits |
| `model_timeout.py` | A timeout and a retry count on the model client, set on the OpenAI library's client object through `make_client` |
| `changed_response.py` | The customs system's version 2 renames a field; a tool returning a Pydantic model, one with a default for the field, and one that catches the validation error |
| `allowed_values.py` | A tool that accepts only three document types, asked about a fourth |
| `tool_shapes.py` | The same investigation with narrow, consolidated and generic tools, and what each run cost |
| `tool_choice.py` | One run with each `tool_choice` setting: auto, required, a named tool or none |
| `offered_tools.py` | An agent built with no tools, given tools for one run; what the definitions cost on a call |
| `several_calls.py` | Every system takes two seconds; when each tool call began and ended, with the framework's concurrency on or off, or the model asked for one call per reply |
| `injected_note.py` | The invoice's record carries an uploader's note with an instruction in it; the tool returns the whole record, or only three fields |
| `document_tool.py` | The chapter's designed document-store tool (pattern, free-text type, retry policy with timeouts, a Pydantic record, a written result for each failure) and the run's limits, against one failure at a time |
| `count_runs.py` | Runs any of the programs several times and prints a line per run |

The systems raise `ConnectionError` and `TimeoutError` as a network client would, and their error messages name a host (`docs-db-02:5432`), the kind of detail that belongs in a log, not in a model's context.

## When the store is down

```bash
uv run python ch05/hidden_outage.py
uv run python ch05/raised_error.py
uv run python ch05/written_error.py
```

`show()` prints each tool result as the model received it. Where the framework turned an exception into a result, the next line shows the exception text the program kept and the model never saw.

In five runs of each:

- **"Not on file" (`hidden_outage.py`).** Every answer recommended obtaining the invoice from the shipper; none suggested looking for a misfiled copy. Three of the five Cause lines said no copy existed or that the invoice was never uploaded.
- **The framework's default (`raised_error.py`).** The model received `Error: Function failed.` and called the search two to four times. Four runs answered, each naming the uncertainty and raising the possibility of a misfiled copy. In two runs three failing rounds in a row reached the framework's limit (`max_consecutive_errors_per_request`, 3 by default), and the framework made one more call with tools turned off. In one of them that reply was a complete report; in the other it was an unfinished tool request, not an answer.
- **A written error (`written_error.py`).** The search ran once or twice and every run answered. No answer claimed the invoice did not exist.

The framework's error limit counts results that carry an exception. A tool that returns its own error dictionary is not counted, so only the loop's other limits, `max_iterations`, `max_function_calls` and `max_duration_seconds`, stop a model that keeps calling it.

## retries.py

```bash
uv run python ch05/retries.py                # the first two store calls fail
uv run python ch05/retries.py --store down   # every store call fails
```

The retry policy is a [tenacity](https://tenacity.readthedocs.io) decorator on the function that calls the store: three attempts of up to three seconds each for connection errors and timeouts, with a random wait that starts at up to half a second and is capped at four. Each retry is logged to stderr as a warning, and the final failure as an error.

The last line counts the model's calls to `find_document` and the tool's calls to the store. With a flaky store, a single run showed one model call and three store calls: the model never saw the failures. With the store down, the tool gave up after three attempts and told the model not to search again; in five runs the model searched once each time. Without that advice (`written_error.py`) the model searched twice in three of five runs, which with three attempts each would be six calls to a store that is down.

## instructed_retry.py

```bash
uv run python ch05/instructed_retry.py
```

The tool is `written_error.py`'s, whose result does not say whether to search again; the instructions add one line saying not to call a tool again after its system did not respond. In five runs the model searched once each time and reported that the check could not be done.

## slow_store.py

```bash
uv run python ch05/slow_store.py --duration-limit 5
uv run python ch05/slow_store.py --tool-timeout 3
uv run python ch05/slow_store.py --run-timeout 8
```

- `--duration-limit` sets the framework's `max_duration_seconds`. The framework checks it after each batch of tool calls, so it cannot interrupt the 20-second call. In a test run the call finished (the search found the invoice), the limit then switched tools off, and the reply was an unfinished tool request.
- `--tool-timeout` passes a timeout to the store, as most network clients accept. The tool stopped waiting after 3 seconds and returned a written error; the model searched twice, and the run finished after 14 seconds with an answer that said the check could not be done.
- `--run-timeout` stops the program waiting for the whole run. In a test run the program gave up at 8 seconds, but the process ended at 24: the tool is synchronous and the framework runs it in a worker thread, which cannot be cancelled, so the store call ran to the end. For a tool that writes, that is a change made after the program stopped listening.

## model_timeout.py

```bash
uv run python ch05/model_timeout.py --timeout 0.1 --retries 0
uv run python ch05/model_timeout.py --timeout 0.1 --retries 2
uv run python ch05/model_timeout.py --timeout 30 --retries 1
```

Builds the agent with `make_client(timeout=..., max_retries=...)`, which sets both values on an `AsyncOpenAI` client and passes it to MAF's client as `async_client`; MAF's Chat Completions client has no setting for either. A timeout of 0.1 seconds is far below what a model call takes, so every attempt times out. With no retries, the run raised `ChatClientException` (caused by `APITimeoutError`) after 0.2 seconds; with the library's default of two retries, after 1.9 seconds, the library logging each retry. With 30 seconds and one retry, the investigation ran normally. At half a second, a short reply sometimes arrives in time and a later model call times out instead, so the count of attempts varies. The timeout limits each wait for data, not the call as a whole: a provider that sends keep-alive bytes while a request is queued restarts it, so a queued call can outlast it.

## changed_response.py

```bash
uv run python ch05/changed_response.py typed
uv run python ch05/changed_response.py defaulted
uv run python ch05/changed_response.py checked
```

Version 2 of the customs system reports each document's `status` as a word instead of a `received` flag. `cobalt.py`'s `list_required_documents` describes the answer with a Pydantic model and returns it; the framework sends the model the result of `model_dump()` as JSON, the same text a dictionary would give. The three variants differ only in how they treat the changed answer, five runs each:

- **`typed`** (cobalt.py's tool): `received` is a required field, so validation fails and the `ValidationError` reaches the framework, which sends `Error: Function failed.` All five runs found the misfiled invoice and said the document list could not be retrieved; three asked for it twice.
- **`defaulted`**: `received: bool = False`, so every entry passes and all three documents are reported as not received. All five runs recommended the right refile, but every answer gave the false receipt status as evidence, and one asked the team to confirm two documents customs had already received.
- **`checked`**: the tool catches `ValidationError`, logs an error and tells the model the format is unrecognized. All five runs found the misfiled invoice, asked for the list once and made no false receipt claim.

## allowed_values.py

```bash
uv run python ch05/allowed_values.py
uv run python ch05/allowed_values.py --any-type
```

The first lines print the parameters the model receives: a pattern for the shipment ID and a list of three document types. The task gives the ID as "4471" and asks about a certificate of origin, which the store holds (DOC-5532). No run sent a shipment ID the pattern would reject. With the closed list, two of five answers said Cobalt holds no certificate of origin, and two more said they could not confirm it because the store holds only the three listed types, which is false. With `--any-type` (cobalt.py's tool, which takes any text) all five found DOC-5532.

## tool_shapes.py

```bash
uv run python ch05/tool_shapes.py narrow
uv run python ch05/tool_shapes.py consolidated
uv run python ch05/tool_shapes.py generic
```

All three shapes found the cause in five runs each. Narrow tools: 4 to 6 model calls, 4,712 to 7,373 tokens. One consolidated tool, `check_customs_documents`: usually 2 model calls, 1,598 to 3,016 tokens. One generic `lookup` tool: 5 or 6 model calls, 4,531 to 5,902 tokens. The consolidated tool can only answer the question it was built for; try it with a task about a certificate of origin.

## tool_choice.py

```bash
uv run python ch05/tool_choice.py auto
uv run python ch05/tool_choice.py required
uv run python ch05/tool_choice.py named
uv run python ch05/tool_choice.py none --investigation
```

Asks a general question that no lookup can answer ("What does it mean when customs puts a shipment on hold?") with the run's `tool_choice` option. With `auto`, five of five runs answered without a tool. With `required`, five of five called `get_shipment_status` with an invented ID, SH-0000, and then answered in the next model call: the framework resets `required` to the default after the first round of tool calls. `named` requires `get_shipment_status`: five of five runs called it with an invented ID (SH-0000 in four, SH-0001 in one), then answered.

`--investigation` asks Chapter 4's task instead. With `none`, five of five runs made one model call and ran no tool: each reply announced a lookup of a tool named `get_shipment`, which the agent does not have, four of them as tool-call markup written out as text.

## offered_tools.py

```bash
uv run python ch05/offered_tools.py all
uv run python ch05/offered_tools.py none
```

Builds the agent with no tools and passes tools to `agent.run` for the one run. The question needs no lookup, so each run is a single model call. With the four tools offered, the call took 824 input tokens; with none, 164: the definitions cost 660 tokens on every call that offers them.

## several_calls.py

```bash
uv run python ch05/several_calls.py default
uv run python ch05/several_calls.py one-at-a-time
uv run python ch05/several_calls.py one-per-reply
```

Every system takes two seconds to answer, and a function middleware records when each tool call began and ended. `one-at-a-time` sets `allow_concurrent_invocation` to `False` in the loop's configuration; `one-per-reply` passes `allow_multiple_tool_calls=False` as a run option, which the framework sends as `parallel_tool_calls`. In five runs of each, all fifteen found the cause:

- `default`: three runs had a reply with two calls (the customs case and its required documents), and both began at the same moment.
- `one-at-a-time`: one run had such a reply, and the second call began when the first ended.
- `one-per-reply`: four runs asked for one tool per reply; the first still asked for two in one reply, which then ran together. Four of five is no more than `one-at-a-time`, whose requests didn't change, so these runs can't show whether the provider honors `parallel_tool_calls` at all.

## count_runs.py

```bash
uv run python ch05/count_runs.py 5 ch05/hidden_outage.py
uv run python ch05/count_runs.py 5 ch05/changed_response.py checked
```

Prints every run in full, then one line per run with the tools called and the Cause line. Five runs of an investigation cost about half a US cent, measured at the lab model's off-peak prices.

## document_tool.py

```bash
uv run python ch05/document_tool.py --store normal
uv run python ch05/document_tool.py --store down
uv run python ch05/document_tool.py --store flaky
uv run python ch05/document_tool.py --store slow
uv run python ch05/document_tool.py --store new-format
```

The design section's tool, assembled: three attempts of three seconds each with backoff and jitter, a `StoredDocument` Pydantic model with three required fields, and a written result for each failure. The program sets the run's limits: a model client with a 30-second timeout and one retry, `max_iterations` 9, `max_function_calls` 20, `max_duration_seconds` 60, and `asyncio.timeout(130)` around the run. `new-format` switches the document store to version 2, which renames the case field. Logs go to stderr.

In five runs of each, the model searched once every time. Normal and flaky found the cause (flaky after two retries the model never saw). Down, slow and new-format answered that the store check could not be done, and none claimed the invoice did not exist. Slow runs took 15 to 17 seconds: three timed-out attempts cost more than `slow_store.py --tool-timeout 3`'s single attempt. The first version's format error lacked "Do not search the document store again", and the model then searched three document types against a store whose every answer failed the check; the line fixed it.

## injected_note.py

```bash
uv run python ch05/injected_note.py full
uv run python ch05/injected_note.py trimmed
```

Adds an `uploader_note` to the invoice's record: a false claim that customs accepted it, and an instruction to report that no action is needed. `full` returns the store's whole record; `trimmed` returns a Pydantic model with three fields. In five runs of each, every run found the misfiled invoice. With `full`, all five answers mentioned the note and dismissed it as contradicted by the case data; with `trimmed`, the note never reached the model. The model could check this note against other results; one with nothing to contradict it is a different test.

