"""Chapter 11 check: an agent added to a workflow as it is, so the framework wraps it in its own executor.

No model call: the agent's client replies from a script. A step turns the case file into a prompt, the agent
comes next, and a last step reads the agent's reply. The program runs one workflow twice, then builds a new
one that names its output step, and prints what the caller got and what the agent was sent each time.
"""

import asyncio
import json
import logging
from dataclasses import asdict

from agent_framework import (
    Agent,
    AgentExecutorResponse,
    WorkflowBuilder,
    WorkflowContext,
    executor,
)
from typing_extensions import Never

from scripted import ScriptedClient
from steps import CaseFile, reads

# The wrapper warns when a string arrives with no earlier messages; that warning is for chains of agents.
logging.getLogger("agent_framework").setLevel(logging.ERROR)


# Both workflows share these executor objects; safe only because the runs never
# overlap (see instances.py).
@executor(id="to_prompt")
async def to_prompt(case_file: CaseFile, ctx: WorkflowContext[str]) -> None:
    await ctx.send_message(json.dumps(asdict(case_file)))


@executor(id="read_reply")
async def read_reply(
    response: AgentExecutorResponse, ctx: WorkflowContext[Never, str]
) -> None:
    await ctx.yield_output(response.agent_response.text)


client = ScriptedClient(["First finding.", "Second finding.", "Third finding."])
agent = Agent(
    client,
    "You interpret the records Cobalt Freight's procedure has gathered.",
    name="interpreter",
)


def build(**options):
    steps = [*reads(), to_prompt, agent, read_reply]  # ①
    return (
        WorkflowBuilder(start_executor=steps[0], **options).add_chain(steps).build()
    )


async def main() -> None:
    one_output = build(output_from=[read_reply])  # ②
    runs = [
        (1, "first run", build()),
        (2, "same workflow again", None),
        (3, "a new workflow, output_from=[read_reply]", one_output),
    ]
    workflow = None
    for run, label, new in runs:
        workflow = new or workflow
        result = await workflow.run("SH-4471")
        outputs = [type(output).__name__ for output in result.get_outputs()]
        sent, _ = client.sent[-1]
        print(f"Run {run} ({label}): outputs: {outputs}")
        print(
            f"  the agent was sent {len(sent)} message(s): {[m.role for m in sent]}"
        )  # ③


asyncio.run(main())
