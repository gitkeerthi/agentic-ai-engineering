# Chapter 2 Labs: From Programs to Agents

Three programs, each a single model call or a single tool call, with no agent framework. Run them from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording from the chapter.

| Program | Shows | Chapter |
|---|---|---|
| `ask_without_tools.py` | A model asked about a shipment it has never seen | Example 2-5 |
| `next_token.py` | Next-token probabilities, and the effect of temperature | Examples 2-6 and 2-7 |
| `raw_tool_call.py` | One tool call on the wire: request, execution, answer | Examples 2-8 to 2-12 |

## ask_without_tools.py

```bash
uv run python ch02/ask_without_tools.py
uv run python ch02/ask_without_tools.py "Which container ship is SH-4471 on?"
```

**Try:** ask for a specific fact the model cannot know, such as a vessel name, a date or a customs case number. Sometimes the model says it doesn't know. Sometimes it invents a plausible answer. Run the same question a few times and watch for both.

## next_token.py

```bash
uv run python ch02/next_token.py
uv run python ch02/next_token.py "Name one European port in one word."
```

With a question argument, the program shows the top five candidates for the first token of the reply, then asks the question three times at temperature 1.0 and three times at 0.

**Try:**

- A question with one obvious answer, such as the port question above. In a test run "Rot" (the start of Rotterdam) took 100% of the probability, so every call at both temperatures said Rotterdam. Temperature only changes the output when the model spreads probability across several candidates.
- An open question, such as `"Suggest one name for a new logistics company. Reply with the name only."`. In a test run the probability spread across "C" (47%), "Swift" (22%) and "North" (13%). The three temperature 1.0 replies were Cargolink, Cargolux and CargoNexa; the three temperature 0 replies were all Cargolux. Ask for a short reply: the program stops each reply at 60 tokens.
- The same open question twice. Compare the temperature 0 replies across the two runs: they usually match, but nothing guarantees it.

## raw_tool_call.py

```bash
uv run python ch02/raw_tool_call.py
uv run python ch02/raw_tool_call.py "Is shipment SH-9999 on track?"
uv run python ch02/raw_tool_call.py "What does demurrage mean in shipping?"
```

The only shipment the tool knows is SH-4471.

**Try:**

- **An unknown shipment** (SH-9999). The model still asks for the tool, and the tool returns an error. The model reads the error, tells the user no shipment was found, and suggests checking the ID. In one run it added that shipment IDs "typically look like `SH-4471`", taken from the example in the tool's description. The error is data the model reasons about, not an exception that stops the program.
- **A general question** (demurrage). The model answers from its own knowledge and asks for no tool, because none is needed. The model, not the code, decides whether to use a tool.
- **A question that names no shipment**, such as `"Why is my shipment late?"`. Watch whether the model asks the user for an ID or guesses one. In our run it asked for no tool. It asked the user for the ID instead, and offered the example value from the tool's description as a hint: the ID, it said, looks like "SH-4471".

## Provider documentation

The programs call DeepSeek through its OpenAI-compatible Chat Completions API, with thinking mode disabled in `agentlab/llm.py`. Provider behavior and model aliases can change; see DeepSeek's [Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/) and [Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/) guides.
