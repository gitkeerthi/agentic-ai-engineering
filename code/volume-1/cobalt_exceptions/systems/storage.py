"""Where the stand-in systems keep their data: one JSON file per system in a state folder.

The folder is `.cobalt/` under the current directory unless COBALT_STATE names another, so that
an investigation, an approval and a release check can run as separate processes. A file per system
is fine for one machine and one user at a time; Chapter 25 replaces it with a database.
"""

import json
import os
from pathlib import Path


def folder() -> Path:
    path = Path(os.environ.get("COBALT_STATE", ".cobalt"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def load(name: str, default=None):
    path = folder() / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else default


def save(name: str, data) -> None:
    (folder() / f"{name}.json").write_text(json.dumps(data, indent=2))
