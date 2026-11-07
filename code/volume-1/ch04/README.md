# Chapter 4 Labs: A First Agent in Microsoft Agent Framework

Chapter 3's investigation agent, rebuilt with Microsoft Agent Framework (MAF). The model, instructions, tools and stand-in records are Chapter 3's, word for word; only the code around them changes. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different number of turns, from the chapter.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0.

The chapter's listings of real output were recorded on two releases. Examples 4-4, 4-11 and 4-12 come from the release above. Examples 4-5, 4-7, 4-9, 4-10, 4-13 and 4-16 were recorded on agent-framework-core 1.19.0 with agent-framework-openai 1.14.4, and the framework behavior they show was checked again on 1.24.0. The one change that check found, in what a span records when a tool raises, is why Example 4-12 was recorded again on 1.24.0.

| File | What it is | Chapter |
|---|---|---|
| `cobalt.py` | Chapter 3's stand-in records, and its four tools written as Python functions that the framework describes to the model | Example 4-3 |
| `investigate.py` | The agent: a chat client, instructions and tools, run once | Examples 4-1 and 4-5 |
| `show_tool_schema.py` | Prints the description the framework builds from `find_document`. No model call. | Example 4-4 |
| `show_history.py` | Runs the agent and prints the history the framework built, read back from the response | Examples 4-6 and 4-7 |
| `traced.py` | Runs the agent with tracing on and prints the trace as a tree; `--check-claims` adds Chapter 3's claim-checking rule to the instructions | Examples 4-8 to 4-11 |
| `step_limit.py` | Runs the agent with a limit of two rounds of tool calls, and checks whether the run reached it | Examples 4-13 and 4-14 |
| `exception_in_span.py` | Makes a tool raise with tracing on, and prints what reached the log and the span with sensitive data off, or on with `--sensitive`. No model call. | Example 4-12 |
| `check_answer.py` | Runs the agent and checks its answer: the three headings, and where each ID in it first appeared | Examples 4-15 and 4-16 |

`agentlab/tracing.py` holds the exporter that prints the tree. `agentlab/llm.py`'s `make_client()` (Example 4-2) builds the chat client; it gives every call the same model setting Chapter 3's `chat()` uses and records each call's token usage (see "What the examples cost" in the repository README).

## investigate.py

```bash
uv run python ch04/investigate.py
```

It prints `result.text`, as the framework's documentation does. In a test run the agent found the misfiled invoice, and the printout began with three one-sentence narrations run together ("...to see what's blocking it.The shipment is held at Rotterdam customs...") before the answer. `text` joins the text of every message the run produced. The final reply is `result.messages[-1].text`, which the other programs print. It usually holds the answer alone, but it can still open with a note: the SH-5120 runs below began their final reply with a sentence or a paragraph of reasoning.

## show_tool_schema.py

```bash
uv run python ch04/show_tool_schema.py
```

Compare the output with `find_document`'s entry in `ch03/cobalt.py`. The name, description, parameter names and parameter notes are the same; the framework adds a `title` to each parameter and to the parameter list. Those titles make the four tool descriptions 80 tokens longer: the first call of every SH-4471 run here reads 817 tokens, against 737 in Chapter 3's Example 3-1.

## show_history.py

```bash
uv run python ch04/show_history.py
uv run python ch04/show_history.py "Shipment SH-9999 is late. Find out why."
```

The same "Model says / Model asks / Result" lines as Chapter 3's trace, rebuilt from `result.messages` after the run.

**Try:**

- **The default run.** In a test run the history held 9 messages. They start with the model's first request: the response holds what the run added, not the instructions and the task. When the model asked for two tools in one turn, both results arrived in a single message, so the count runs lower than Chapter 3's.
- **An unknown shipment** (SH-9999). In a test run the agent stopped after one lookup and reported that the shipment does not exist, as Chapter 3's agent did.

## traced.py

```bash
uv run python ch04/traced.py
uv run python ch04/traced.py "Shipment SH-5120 is late. Find out why."
uv run python ch04/traced.py --max-iterations 2
uv run python ch04/traced.py --check-claims "Shipment SH-5120 is late. Find out why."
uv run python ch04/traced.py --check-claims
```

The answer comes first, then the trace: one `invoke_agent` span for the run, a `chat` span for each model call and an `execute_tool` span for each tool call. Tracing records prompts, replies, tool arguments and results (`enable_sensitive_data=True`), which is right for a laptop and wrong for production without access control and a retention policy.

**Try:**

- **The default run.** Read the `chat` lines from top to bottom: in a test run the tokens read went 817, 936, 1037, 1165, 1292, 1395, and every call ended `tool_calls` except the last, which ended `stop`.
- **The false premise from Chapter 3** (SH-5120). In a test run the first result showed the shipment in transit and due next Wednesday; the agent went on to search for all three documents, then answered that it could find no cause and recommended confirming the carrier's arrival time. Chapter 3's Example 3-10 shows the same failure, and its "Finding the Part to Fix" shows the fix, which `--check-claims` applies here.
- **The claim-checking rule** (`--check-claims`). Adds Chapter 3's paragraph, word for word, to the instructions. In a test run on SH-5120 the agent looked up the shipment and the commercial invoice, said the shipment isn't late, and stopped after three model calls instead of four. On SH-4471 it still found the misfiled invoice, in four calls, and added a note that the records confirm the hold but not the lateness the task claims. The paragraph adds 36 tokens to every call.
- **A limit of two rounds of tool calls.** The trace shows a third `chat` span: the framework's extra call with tools turned off. Nothing in the trace flags the run as cut off; `step_limit.py` shows how to tell.

**Viewing the trace in Jaeger.** The same spans can go to a trace viewer. Start Jaeger in Docker, run with the traces endpoint set, then open http://localhost:16686 and pick the service `agent_framework`:

```bash
docker run -d --name jaeger -p 16686:16686 -p 4317:4317 jaegertracing/jaeger:2.22.0
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4317 uv run python ch04/traced.py
```

Use the traces endpoint, not `OTEL_EXPORTER_OTLP_ENDPOINT`: the general variable sends logs and metrics too, which Jaeger doesn't accept, and the run prints "Failed to export logs" errors.

## step_limit.py

```bash
uv run python ch04/step_limit.py
```

The limit is two rounds of tool calls: `max_iterations` counts the model calls that may ask for tools. When both ask for tools, the framework makes one more call with tools turned off and returns that reply as the run's answer (if the reply were empty, it would substitute the sentence "Function invocation limit reached before a final answer could be produced."). In seven test runs at this limit (one of them `check_answer.py --max-iterations 2`) the reply was never an answer: each time the model wrote a request for a tool that does not exist (`search_documents` and `list_documents` twice each, `get_case_documents`, `list_case_documents`, `get_document_requirements`) as markup in its text. The stop reason was `stop` every time. The program counts the rounds of tool calls in `result.messages`; when the count equals the limit, the run reached it. That check catches only this limit: the framework's other loop limits, including the one on three failing rounds in a row, end a run the same way after fewer rounds (see the chapter). `step_limit.py` and `check_answer.py` are the only programs here that check; the others keep the agent minimal and print its reply as is.

## check_answer.py

```bash
uv run python ch04/check_answer.py
uv run python ch04/check_answer.py "Shipment SH-5120 is late. Find out why."
uv run python ch04/check_answer.py --max-iterations 2
```

Chapter 3's answer check, reading the framework's response instead of a hand-built message list. The answer is `result.messages[-1].text`. The check looks for the three headings at the start of a line, and for each shipment, case and document ID in the answer it finds where the ID first appeared: the task, a tool result (`function_result`), or the model's own text or tool-request arguments (`function_call`). An ID first written by the model fails, even if a tool later echoed it.

**Try:**

- **The default run.** In a test run the check passed. The answer wrote its headings in bold (`**Cause:**`), which the check accepts.
- **The false premise** (SH-5120). In a test run the check passed although the answer recommended asking the carrier about a delay that doesn't exist: every ID came from the task or a tool, and all three headings were there. The check tests form and where the record IDs came from, not whether the conclusion is true.
- **A limit of two rounds.** In a test run the reply was another invented tool request (`get_document_requirements`) and the check failed on all three headings. The check knows nothing about loop limits; it catches the reply because it isn't an answer.

## exception_in_span.py

```bash
uv run python ch04/exception_in_span.py
uv run python ch04/exception_in_span.py --sensitive
```

No model call. A tool that raises is called with tracing on. With sensitive data off (the default), the framework's log line names only the function and the exception type, and the tool's span has status ERROR and an `error.type` attribute, with no message and no `exception` event. With `--sensitive`, the log line, the span's status description and an `exception` event all carry the message, and the event carries the stack trace. Either way the caller gets the exception itself, message included. A model calling this tool would receive only "Error: Function failed."
