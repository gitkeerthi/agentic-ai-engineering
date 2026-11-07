"""One investigation against the real model, run only with `uv run pytest tests -m live` (about $0.001).

The model's answer varies from run to run, so, like Chapter 12's live tests, this one asserts what must
hold on every run: one typed output, one of the designed endings, and no more model calls than the loop
allows. Whether SH-4471's finding is right is the case set's job (`ch15/evaluate.py`, `ch15/score.py`)."""

import asyncio
import typing

import pytest

from agentlab.usage import mark
from cobalt_exceptions.agents.interpreter import LOOP, interpreter
from cobalt_exceptions.agents.steps import investigation
from cobalt_exceptions.domain.contracts import Finding, Flagged, InvestigationRequest, Reason


@pytest.mark.live
def test_sh4471_ends_as_designed_within_the_call_limit():
    request = InvestigationRequest(shipment_id="SH-4471", requested_by="analyst-017")
    limit = LOOP["max_iterations"] + 1  # the loop's calls, plus the last one with tools off
    before = mark()
    [output] = asyncio.run(investigation(interpreter()).run(request)).get_outputs()
    assert mark() - before <= limit
    if isinstance(output, Flagged):
        assert output.reason in typing.get_args(Reason) and output.problems
    else:
        assert isinstance(output, Finding)
