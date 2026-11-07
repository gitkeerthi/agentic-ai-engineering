# Agentic AI Engineering, Volume 1: Code

Runnable examples for *Agentic AI Engineering, Volume 1: Agent Foundations and Quality Engineering*, the first volume of a series about designing and building AI agents for enterprise systems. There is one folder per chapter that has programs (Chapter 1, the introduction, has none). Each program is small and shows one idea, and each folder's README lists experiments you can run without changing any code.

The examples follow Cobalt Freight, a fictional logistics company, and shipment SH-4471, a container held in a Rotterdam customs yard. All company data is made up and lives in the programs themselves.

## The example in brief

When a container reaches a border, customs opens a **customs case** for it and keeps the goods in the yard until every document the case requires has arrived. For Cobalt's shipments those are the **bill of lading** (the carrier's receipt for the goods), the **commercial invoice** (what was sold, to whom and for how much) and the **packing list**. Cobalt uploads each document to its document store and **files** it against the shipment's customs case; that is how customs receives it.

SH-4471's invoice was uploaded, but filed against another shipment's case. Customs saw it as missing and put the container **on hold**. **Refiling** the invoice against the right case fixes it. That is the problem the agents in this repository investigate, and in later chapters, the fix they may request.

The IDs tell you what kind of record you are looking at:

| Prefix | Record | Example |
|---|---|---|
| SH- | A shipment | SH-4471, the held container of industrial pumps |
| RTM- | A customs case at Rotterdam | RTM-88213, SH-4471's case |
| DOC- | A document in Cobalt's document store | DOC-5531, SH-4471's commercial invoice |
| MSG- | A customs message or carrier notice in Cobalt's message archive (from Chapter 15) | MSG-7104, customs' rejection of SH-4731's unsigned invoice |

## Setup

You need [uv](https://docs.astral.sh/uv/) and an API key for a model provider. Clone the repository once: it holds every volume's code, each under `code/volume-N/`. Run every command for this volume from this folder, `code/volume-1/`: the book's listings start from here, and the programs import `agentlab/` and `cobalt_exceptions/` from it. The programs need Python 3.13, which uv downloads if it isn't installed. Chapter 14 also runs Langfuse in Docker (see [ch14/README.md](ch14/README.md)).

```bash
git clone https://github.com/gitkeerthi/agentic-ai-engineering.git
cd agentic-ai-engineering/code/volume-1
cp .env.example .env      # then replace the placeholder key in .env with yours
uv sync
uv run python ch02/next_token.py
```

The examples call DeepSeek's models through the OpenAI Python SDK, which works because DeepSeek's API follows OpenAI's format. To use another provider with an OpenAI-compatible API, change `agentlab/llm.py`: it is the only file that knows the provider.

Model replies vary from run to run, so your output will differ in wording, and sometimes in substance, from the output quoted in the book.

## Chapters

| Folder | Chapter | What the programs show |
|---|---|---|
| [ch02/](ch02/README.md) | 2. From Programs to Agents | One model call, next-token probabilities and temperature, one tool call on the wire |
| [ch03/](ch03/README.md) | 3. Anatomy of an Agent | An agent loop written by hand, how instructions change behavior, a task with a false claim, a check on the final answer, and the original text-based ReAct loop |
| [ch04/](ch04/README.md) | 4. A First Agent in Microsoft Agent Framework | Chapter 3's agent rebuilt with the framework: the history read back from the response, a trace of the run, and what happens at the step limit |
| [ch05/](ch05/README.md) | 5. Tools and Failure Recovery | Tools that call stand-in systems that fail: a hidden outage, the framework's default error, written errors, retries, time limits, a changed answer, tool shapes, tool choice, an injected instruction, and a designed document-store tool |
| [ch06/](ch06/README.md) | 6. State and Context Engineering | An agent that forgets between runs, a session, saving it across a restart and a failed run, what one model call contains and how it grows, each compaction strategy on the same conversation, and findings kept outside the history |
| [ch07/](ch07/README.md) | 7. Context Providers | An agent whose session history goes out of date, two simple fixes, the provider pipeline, a provider for current records and where its note lands, a file-backed history that repairs itself, and four providers on one agent |
| [ch08/](ch08/README.md) | 8. Middleware and Agent Hooks | Cross-cutting code around runs, model calls, and tool calls; audit, limits, stopping, and fail-closed interception |
| [ch09/](ch09/README.md) | 9. Tool Approval and Human Gates | A refiling tool held for approval and answered in another process; what the framework binds, stale approvals, lost replies and idempotency keys, and the refiling gate |
| [ch10/](ch10/README.md) | 10. Structured Output and Contracts | The finding as a Pydantic contract; JSON mode, a refused schema request and the answer as a tool call; three layers of checks, one repair, and strict mode tested |
| [ch11/](ch11/README.md) | 11. Basic Workflows | A written procedure in the instructions against the same procedure as a workflow: executors, edges and a run; what the builder checks; one agent step and a check step; failed steps and their endings |
| [ch12/](ch12/README.md) | 12. Testing Agentic Applications | A pytest suite for the investigation: unit, contract, component and workflow tests with scripted replies, recorded model replies (VCR cassettes) and snapshots, a few live tests, and a first case set with known answers |
| [ch13/](ch13/README.md) | 13. Evaluating Agent Outcomes | Two versions of the investigation agent's instructions compared on a golden set that keeps development cases apart from challenge cases written to test the change (it has no held-out sample): every run saved and scored offline by code checks, a rubric and an LLM judge (checked against labels and planted errors), pass rates with intervals; an agent's tool calls evaluated with the framework's `evaluate_agent()` |
| [ch14/](ch14/README.md) | 14. Observing Runs and Measuring Cost | The investigation traced as a whole with OpenTelemetry (workflow, step, read, agent, model and tool spans), its configuration on every trace, one ID across trace, case record, evidence store and logs, trace context carried to a second process; a wrong finding reconstructed and its request replayed; tokens, latency and cost per run and per success, for two versions and two models |
| [ch15/](ch15/README.md) | 15. Project 1: An Evaluated Exception Research Agent | The application package `cobalt_exceptions/` (later projects extend it) and its tests in `tests/`: a workflow with one agent that searches Cobalt's messages, a typed finding checked against the records, a case lifecycle, and a refiling gate that files only what a checked finding names; the `cobalt` command; an evaluation on fifteen cases, twenty-two designed failures, and a trace reader |

`agentlab/` holds the code every chapter shares:

- `llm.py`: `chat()`, which makes one call to the model; `describe_tool()`, which writes a tool description in the format the model receives; and `make_client()`, which builds Microsoft Agent Framework's chat client for the same model (Chapter 4 onwards).
- `tracing.py`: an OpenTelemetry exporter that prints an agent run's trace as a tree in the terminal.
- `usage.py`: the usage log described below, and `mark()` and `since()`, which total the calls one program run makes (Chapter 11).

From Chapter 15, the application itself lives in `cobalt_exceptions/`, with its tests in `tests/` (`uv run pytest tests`) and its dependency rule in `pyproject.toml` (`uv run lint-imports`). Run it with `uv run cobalt --help`.

## What the examples cost

Every model call made through `chat()` or `make_client()` appends its token counts to `usage.jsonl` in this folder. The file stays on your machine (it is git-ignored). To see what this month's calls have cost:

```bash
uv run python -m agentlab.usage
```

The prices in `agentlab/llm.py` were copied from the provider's pricing page on 2026-10-31, with its peak and off-peak rates; check them against the current page. One run of the Chapter 4 investigation agent on SH-4471 (six calls, most of the input served from the provider's cache) cost about $0.0005 off-peak, and would cost about twice that at peak.

## License

The code is released under the MIT License: see [`LICENSE`](../LICENSE), which covers every volume's code in this repository. `ch14/langfuse/compose.yml` is adapted from Langfuse's own and stays under Langfuse's MIT license, in `ch14/langfuse/LICENSE-langfuse`. The books' text and figures are not covered by this license.
