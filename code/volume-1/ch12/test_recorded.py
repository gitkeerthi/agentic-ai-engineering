"""Chapter 12 integration tests: the case set, run through the real chat client with the model's replies
replayed from recordings.

Everything runs as it would in production (our code, the framework, the provider's client library and its HTTP
requests) except the network: each request is answered from a cassette in cassettes/test_recorded/. A request
whose method, URL or body (compared as parsed JSON) differs from the recording fails the test. Each test asserts the typed outcome a person
approved when the reply was recorded (a snapshot in __snapshots__/test_recorded/), so a code change that
handles the same reply differently fails. Record against the real model, then review and accept the outcomes:

    uv run pytest ch12 --record-mode=rewrite --snapshot-update    # one model call per agent case

Replay, for free:

    uv run pytest ch12/test_recorded.py -v
"""

import asyncio

import pytest

from syrupy.extensions.json import JSONSnapshotExtension

from case_set import CASES, answer
from steps import interpreter


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": ["authorization"],  # keep the API key out of cassettes ①
        "match_on": ["method", "uri", "body"],  # the same request, or no reply ②
        "decode_compressed_response": True,  # keep the replies readable
    }


@pytest.fixture(autouse=True)
def no_usage_log(record_mode, monkeypatch):
    """A replayed reply costs nothing: agentlab mustn't log it as a call."""
    if record_mode == "none":
        monkeypatch.setattr("agentlab.llm.record", lambda *usage: None)


@pytest.mark.vcr  # ③
@pytest.mark.parametrize("case", CASES, ids=[c["shipment_id"] for c in CASES])
def test_case_set_replayed(build, case, snapshot):
    [output] = asyncio.run(
        build(interpreter()).run(case["shipment_id"])  # ④
    ).get_outputs()
    assert answer(output) == snapshot.use_extension(JSONSnapshotExtension)  # ⑤
