"""Fixtures for the application's tests: a fresh state folder with the seeded stand-in records for
every test, and live tests skipped unless asked for with `-m live` (they call the real model)."""

import pytest

from cobalt_exceptions.systems import records


def pytest_collection_modifyitems(config, items):
    if "live" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="calls the real model; run with -m live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls the real model and costs money")


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("COBALT_STATE", str(tmp_path))
    records.reset()
    return tmp_path
