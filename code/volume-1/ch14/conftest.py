"""Fixtures for the telemetry tests: telemetry set up once for the session (a process can configure
OpenTelemetry only once), into a fresh store, and Cobalt's records put back around each test."""

import shutil

import pytest

import cobalt
import telemetry


@pytest.fixture(scope="session")
def store():
    shutil.rmtree(telemetry.HERE / "store" / "tests", ignore_errors=True)
    path = telemetry.setup("tests")
    yield path
    telemetry.close()


@pytest.fixture(autouse=True)
def records():
    cobalt.reset()
    yield
    cobalt.reset()
