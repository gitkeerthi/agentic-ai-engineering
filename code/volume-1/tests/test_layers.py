"""The dependency rule: each layer imports only the layers beneath it; the domain, systems and
services never import the framework or the model client; only the services may file. The rules are
in pyproject.toml; import-linter checks them."""

import subprocess
from pathlib import Path


def test_the_layers_hold():
    result = subprocess.run(
        ["lint-imports"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout
    assert "Contracts: 3 kept, 0 broken." in result.stdout
