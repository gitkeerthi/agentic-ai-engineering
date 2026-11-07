"""Fixtures every Chapter 12 test shares: Cobalt's records put back around each test, and the workflow to test.

uv run pytest ch12                  # every test that needs no model
uv run pytest ch12 --with-change    # the same tests, on the workflow with the_change.py's edit
uv run pytest ch12 -m live          # the tests that call the real model
"""

import pytest

import cobalt
from steps import investigation
from the_change import investigation_with_change


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls the real model and costs money")


def pytest_collection_modifyitems(config, items):
    """Skip live tests unless the run asked for them, however pytest was started."""
    if "live" in (config.getoption("-m") or "").replace("not live", ""):
        return
    for item in items:
        if "live" in item.keywords:
            item.add_marker(
                pytest.mark.skip(reason="calls the real model; use -m live")
            )


def pytest_addoption(parser):
    parser.addoption(
        "--with-change",
        action="store_true",
        help="test the workflow with the_change.py's document check",
    )


@pytest.fixture(autouse=True)  # ①
def records():
    """Each test starts from the same records, whatever the last one changed."""
    cobalt.reset()
    yield
    cobalt.reset()


@pytest.fixture
def build(request):  # ②
    """The function that builds the workflow under test."""
    if request.config.getoption("--with-change"):
        return investigation_with_change
    return investigation
