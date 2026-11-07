"""Chapter 12 end-to-end tests: the whole investigation against the real model and the stand-in records.

The model's answer varies from run to run, so these tests assert what must hold on every run, not the answer:
one typed output, one of the endings the workflow was designed to reach, and no more model calls than the
agent's configuration allows: its tool-call rounds plus the last call the framework makes with tools off.
Whether the answer is right is the case set's job (run_cases.py). They cost money, so pytest skips them unless
asked:

    uv run pytest ch12 -m live -v    # about one model call per agent case
"""

import asyncio
import typing

import pytest

from agentlab.usage import mark
from case_set import CASES
from contracts import Finding
from steps import Flagged, Reason, interpreter


@pytest.mark.live  # ①
@pytest.mark.parametrize("case", CASES, ids=[c["shipment_id"] for c in CASES])
def test_one_designed_ending_within_the_call_limit(build, case):
    agent = interpreter()
    limit = agent.client.function_invocation_configuration["max_iterations"] + 1  # ②
    before = mark()
    [output] = asyncio.run(build(agent).run(case["shipment_id"])).get_outputs()  # ③
    assert mark() - before <= limit
    if isinstance(output, Flagged):
        assert output.reason in typing.get_args(Reason) and output.problems  # ④
    else:
        assert isinstance(output, Finding)
