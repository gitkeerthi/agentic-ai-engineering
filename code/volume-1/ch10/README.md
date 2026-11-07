# Chapter 10 Labs: Structured Output and Contracts

The investigation agent from Chapter 8, with its answer turned from labeled text into a typed finding that a program can check. The programs show Chapter 6's text extractor failing on the agent's answer, the finding's contract as a Pydantic model, a schema-constrained final answer refused by the provider, the investigation answered in JSON mode, with the schema in the instructions only, and with JSON mode in a final run of its own, the four checks on a reply (JSON, contract, business records, provenance), one repair attempt after a failed check, the finding as the arguments of a tool the agent calls, the framework's behavior around that tool checked with a scripted client, and the provider's strict tool mode tested with requests built to break the schema. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different status, from the chapter's.

Tested with agent-framework-core 1.24.0 and agent-framework-openai 1.18.0, on DeepSeek's `deepseek-flash` with thinking disabled. DeepSeek offers JSON mode (`{"type": "json_object"}`) for final answers but refuses a `json_schema` response format with a 400. Its strict tool mode is a beta feature on `https://api.deepseek.com/beta`; `agentlab/llm.py`'s `chat(..., beta=True)` sends a request there.

| File | What it is |
|---|---|
| `cobalt.py` | Chapter 8's records and the four read tools |
| `contracts.py` | The contract: `Evidence`, `Refiling` and `Finding` (with the cross-field rule `parts_agree`), `check()` (parse, then validate), `provenance_problems()` (every cited record must be one a lookup returned or found; a failed lookup confirms nothing, and neither does the call that reports the finding) and `record_problems()` (claims the records contradict) |
| `investigate.py` | The agent: `INSTRUCTIONS` (Chapter 8's, answering in labeled text) and `JSON_INSTRUCTIONS` (the same, answering with one JSON object that matches the schema generated from `Finding`), the task, `investigator()` and `show()` |
| `prose_parse.py` | The text answer read with Chapter 6's extractor, then asked which document to refile and against which case |
| `schema_request.py` | `response_format=Finding`: the framework sends a `json_schema` response format, and the provider refuses it |
| `json_mode.py` | The investigation with `JSON_INSTRUCTIONS` and JSON mode, with the four checks on its reply. `--prompt-only` leaves JSON mode off |
| `json_after.py` | The investigation with `JSON_INSTRUCTIONS` and no response format, so the notes survive, then a second run on the same session with tools off and JSON mode on that asks for the finding |
| `validate.py` | No model call. `check()` and `record_problems()` on replies written to fail one layer each, and two copied from earlier runs |
| `repair.py` | `JSON_INSTRUCTIONS` without JSON mode; if the reply fails `check()`, one repair message on the same session with tools off |
| `tool_output.py` | The finding as the arguments of `report_finding`, a tool whose parameters are the `Finding`'s fields (`input_model=Finding`) |
| `scripted.py`, `scripted_checks.py` | No model call. A lab-only client that replies from a script, and seven checks: arguments that fail the `Finding` (with and without `include_detailed_errors`), arguments that break `parts_agree`, three failing calls in a row, JSON mode on every call of the loop, `result.value` with and without a sentence before the JSON, findings that cite records no tool confirmed (SH-0042, RTM-51200 after a failed lookup, and SH-0042 reported through `report_finding`), and function middleware that ends the run once `report_finding` has run |
| `strict.py` | Schema helpers for strict tool definitions: `closed()` (`additionalProperties: false` on every object) and `inlined()` (every `$ref` replaced by its definition) |
| `strict_schema.py` | One forced tool call per request on the beta endpoint, no agent: a one-field enum asked for a value it doesn't allow, then the `Finding` asked for arguments that break its enum, a top-level pattern and a pattern inside `refiling`, each under three tool definitions, twenty calls each; the arguments are checked against the exact schema sent, with `jsonschema` |
| `count_runs.py` | Runs a program several times and counts the outcomes it reports |

The SH-5120 task used below is `"Shipment SH-5120 is due next Wednesday. Is anything holding it up?"`.

## Reading the text answer

```bash
uv run python ch10/prose_parse.py
uv run python ch10/count_runs.py 10 ch10/prose_parse.py
uv run python ch10/count_runs.py 10 ch10/prose_parse.py "Shipment SH-5120 is due next Wednesday. Is anything holding it up?"
```

On SH-4471, all 10 answers named both RTM-88124 and RTM-88213, so the program couldn't tell which case to refile against; in 7 of them the evidence was a bulleted list, and the extractor kept its first bullet. On SH-5120, the extractor found a Cause line in 9 of the 10 answers and a Cause heading in the tenth; 7 of the answers said nothing was holding the shipment up. In run 3, the one with headings, the extractor filled Cause and Evidence with the same line; in runs 5 and 8 it found one case to refile against, RTM-5120 and RTM-51200, IDs the model had looked up and found don't exist.

## Asking for JSON

```bash
uv run python ch10/schema_request.py
uv run python ch10/count_runs.py 10 ch10/json_mode.py
uv run python ch10/count_runs.py 10 ch10/json_mode.py "Shipment SH-5120 is due next Wednesday. Is anything holding it up?"
uv run python ch10/count_runs.py 10 ch10/json_mode.py --prompt-only
uv run python ch10/count_runs.py 10 ch10/json_mode.py "Shipment SH-5120 is due next Wednesday. Is anything holding it up?" --prompt-only
```

`schema_request.py` raised `Error code: 400 - This response_format type is unavailable now`. With JSON mode, 10 of 10 replies were valid on SH-4471 (all `cause_found`) and 10 of 10 on SH-5120 (9 `nothing_wrong`, 1 `undetermined`), and all 51 notes before tool calls came back blank: the response format goes with every model call of the run, and DeepSeek replaces non-JSON output with spaces. With the schema in the instructions only, SH-4471 was 10 of 10 valid, SH-5120 5 of 10, and none of the 93 notes was blank. All five failures had text before the JSON object; run 2's reply held two objects, the first citing a placeholder record, SH-0042.

## Checking a reply

```bash
uv run python ch10/validate.py
```

A trailing comma and a sentence before the JSON fail the parse; a missing field, a status outside the three, and a document ID without its prefix fail the contract's types and patterns; "nothing wrong, but a refiling" fails `parts_agree`. A refiling against the wrong case and a `cause_found` finding for SH-5120 pass the contract and fail `record_problems()`.

## Repairing a reply, and JSON mode in a run of its own

```bash
uv run python ch10/count_runs.py 10 ch10/repair.py "Shipment SH-5120 is due next Wednesday. Is anything holding it up?"
uv run python ch10/count_runs.py 10 ch10/json_after.py "Shipment SH-5120 is due next Wednesday. Is anything holding it up?"
```

`repair.py`: 4 of 10 first replies failed with text before the JSON (one inside a code fence); all 4 were valid after one repair, and each repaired reply was the object from the first reply, unchanged. Of the 6 valid first replies, one (run 9) said `cause_found`, which `record_problems()` would reject (this program doesn't run it). `json_after.py`: 10 of 10 valid, all `nothing_wrong`, and none of the 40 notes before tool calls was blank.

## The finding as a tool call

```bash
uv run python ch10/count_runs.py 10 ch10/tool_output.py
uv run python ch10/count_runs.py 10 ch10/tool_output.py "Shipment SH-5120 is due next Wednesday. Is anything holding it up?"
uv run python ch10/scripted_checks.py
```

All 20 runs reported a finding, and none of the 130 assistant messages with text (the notes plus each run's closing reply) was blank. SH-4471: 10 `cause_found`. SH-5120: 7 `nothing_wrong`, 2 `undetermined` and 1 `cause_found`, which `record_problems()` flagged; in one run the first `report_finding` call failed validation, the model was sent "Error: Argument parsing failed.", and its second call passed. The scripted checks: the tool doesn't run on arguments that fail the `Finding`, `parts_agree` included; the model is told why only with `include_detailed_errors=True`; after three failing calls in a row the framework makes one more model call with `tool_choice` set to `none`; JSON mode goes with every model call; `result.value` raises a `ValidationError` on a sentence before the JSON; `provenance_problems()` flags SH-0042 and RTM-51200; and with the middleware, a run that calls `report_finding` makes one model call instead of two. In another batch of ten SH-5120 runs, one ended with no finding: its final text wrote out more lookups as raw markup, which looks like the tools-off final call the framework makes when the loop runs out of iterations (that run's tool calls weren't printed).

## Testing strict mode

```bash
uv run python ch10/strict_schema.py
```

Twenty forced calls per cell. Strict mode refused the `Finding`'s schema as Pydantic writes it, with `Invalid tool parameters schema : field anyOf: missing field type` (likely the `anyOf` for `Refiling | None`, which holds a bare `$ref`), and accepted it with the references inlined. Inlining also removed Pydantic's `$defs` block, and DeepSeek documents definitions under `$def`, so the test can't tell which change it needed. It didn't hold the arguments to the schema: the one-field tool received "pending" for an `open`/`closed` enum in 1 of 20 strict calls (2 of 20 without strict mode) and in 19 of 20 with the field one object down; a shipment ID without its prefix got through in 3 of 20 strict calls (11 of 20 without), and a document ID without its prefix inside `refiling` in 20 of 20 (20 of 20 without). A status outside the enum with an extra field broke the schema in none of the calls, with or without strict mode.

`jsonschema` is a project dependency for this check.
