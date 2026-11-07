# Chapter 3 Labs: Anatomy of an Agent

An agent loop written out by hand, with no framework, so every part of the agent is visible: the instructions, the task, the tools, the message history and the loop that ties them together. Run the programs from `code/volume-1/`, the folder above this one. Replies vary from run to run, so expect different wording, and sometimes a different number of turns, from the chapter.

| File | What it is | Chapter |
|---|---|---|
| `cobalt.py` | Stand-ins for Cobalt's shipment, customs and document systems, and the tool descriptions the model sees | Example 3-4 |
| `loop.py` | The agent loop and the control point that runs each tool request | Example 3-6 |
| `investigate.py` | The SH-4471 investigation agent and its instructions, printed turn by turn | Examples 3-1, 3-2, 3-5, 3-8 and 3-10 |
| `compare_instructions.py` | The same agent with minimal and with detailed instructions | Example 3-3 |
| `react_text.py` | The original ReAct loop: actions written as text and parsed by the code | Example 3-7 |
| `check_answer.py` | The agent's final answer checked for its headings, and for IDs the model brought in from outside the task and the tool results | Example 3-9 |
| `false_premise.py` | A task that states something false, with and without an instruction to check it | Examples 3-11 and 3-12 |

The only shipments the stand-in systems know are SH-4471 (held in Rotterdam customs) and SH-5120 (in transit, due next Wednesday).

## investigate.py

```bash
uv run python ch03/investigate.py
uv run python ch03/investigate.py --max-steps 2
uv run python ch03/investigate.py --max-steps 4
uv run python ch03/investigate.py "Shipment SH-5120 is late. Find out why."
uv run python ch03/investigate.py "Shipment SH-9999 is late. Find out why."
```

Each turn prints how many messages and tokens the model read, what it said, the tool it asked for and the result.

**Try:**

- **The default run.** Watch the token count grow each turn: in a test run it went 737, 850, 954, 1089, 1220. The model rereads the whole history on every turn.
- **A step limit of 2.** The agent is cut off before it finds the cause and returns no answer. In a test run it had just learned that customs was missing a document, two lookups from the cause. The limit belongs to the loop, not the model.
- **A task with a false claim** (SH-5120). Read turn 2: the result in front of the model says the shipment is due next Wednesday, and the model still goes looking for the cause of a delay. In a test run it searched the document store, looked up another shipment's customs case (RTM-88213, taken from the example in a tool description), and after six turns answered that it could find no cause, then recommended work anyway.
- **A step limit of 4, one turn short.** In a test run the agent found, in turn 4, that invoice DOC-5531 is filed against RTM-88124, and the limit ended the run before it could write an answer: the evidence for the cause was in the history, but the program printed "No answer: the agent hit its step limit." That's why a stopped run's history is worth handing to a person.
- **An unknown shipment** (SH-9999). In a test run the agent repeated the same lookup once "to verify the tool isn't just a transient failure", then reported that the shipment doesn't exist and suggested checking the ID.

## compare_instructions.py

```bash
uv run python ch03/compare_instructions.py
uv run python ch03/compare_instructions.py "Shipment SH-5120 is late. Find out why."
```

**Try:** compare the two answers. In a test run both found the misfiled invoice. The differences were in everything around the finding. With minimal instructions, the agent asked for two tools in the same turn, wrote a free-form answer in bold markdown and offered to do more. With detailed instructions, it made one more lookup to check the other customs case, then used the Cause, Evidence and Recommended action format, after two sentences of preamble. The detailed instructions also cost 140 extra tokens on every turn (737 against 597 on the first).

**Try:** the same comparison on the false premise (SH-5120). Neither set of instructions tells the agent to check the task's claims. In a test run, the minimal agent made one lookup in 2 turns, said no delay was recorded and it couldn't find a reason, and offered to search the documents. The detailed agent searched for all three documents, then answered in 4 turns that nothing in Cobalt's systems explained "the delay" and recommended asking the carrier about the Singapore leg. Neither said the shipment wasn't late; the detailed instructions' "keep investigating" line led to more lookups and a recommendation of work.

## false_premise.py

```bash
uv run python ch03/false_premise.py
uv run python ch03/false_premise.py "Shipment SH-4471 is three days late. Find out why."
```

The task says SH-5120 is late. It isn't: it's due next Wednesday.

**Try:** compare the two runs. In three test runs without the check, the agent took 5 to 7 turns. Each answer quoted the due date and still recommended work: checking the due date against the carrier's tracking, lodging a customs declaration, opening a customs case and filing the documents against it. With one paragraph telling it to check the task's claims first, every run stopped after 2 or 3 turns and said there was no delay.

**Try:** the check on a task whose claim is true (SH-4471), to see whether the new rule breaks the case that worked. In three test runs with the check, the agent found the misfiled invoice every time, in 5, 6 and 5 turns. One run said the task's claim "checks out" because the shipment was held: it can't check "three days late" against a calendar, because nothing gives it the date.

Look for a second lesson in the runs without the check: an agent may mention customs case RTM-88213, which belongs to SH-4471, or IDs no tool returned. Example IDs in the tool descriptions are one source; `check_answer.py` catches both.

## check_answer.py

```bash
uv run python ch03/check_answer.py
uv run python ch03/check_answer.py "Shipment SH-4471 is three days late. Find out why."
```

Runs the agent once, prints its answer, then checks it: are the three headings there, and did every shipment, case and document ID in the answer first appear in the task or a tool result?

**Try:** run the SH-5120 task more than once; the check's result can change with the agent's path. In our one saved run the agent investigated SH-4471 as well, recommended refiling SH-4471's invoice, and the check failed: RTM-88213 and SH-4471 were first written by the model, which took them from the examples in the tool descriptions. The SH-4471 task passed.

## react_text.py

The chapter's loop uses tool calling: the model returns each action as structured data. The 2022 ReAct paper, which named the reason-act-observe loop, came before tool calling existed. Its model wrote each step as text, a `Thought:` line and an `Action:` line, and the code found the action with a regular expression, ran the tool and sent the result back as an `Observation:` line. This program rebuilds the investigation agent that way. It also tells the API to stop generating as soon as the model writes "Observation:". Without that stop, the model would carry on and write the tool result itself.

```bash
uv run python ch03/react_text.py
uv run python ch03/react_text.py "Shipment SH-5120 is late. Find out why."
```

**Try:** compare the printout with `investigate.py`. The steps are the same: look up the shipment, the customs case, the required documents, the invoice. Here the model writes each action as a line of text, and the code finds it with a regular expression. If the model writes the line in a different format, the code can't run it. Tool calling, used in `loop.py`, removes that fragility: the action arrives as structured data.

**Try:** the false premise (SH-5120) with the text loop. In a test run the agent made three lookups, one of them `get_customs_case` with the shipment ID SH-5120 instead of a case ID (the tool returned "No customs case found"), and answered that SH-5120 "is late due to an in-transit delay". The plumbing differs from `investigate.py`, and the agent accepts the false premise just the same.
