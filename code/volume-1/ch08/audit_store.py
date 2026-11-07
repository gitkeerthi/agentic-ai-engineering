"""A stand-in for an append-only audit store: one JSON Lines file. `down` makes every write fail."""

import json
from pathlib import Path

PATH = Path(__file__).parent / "audit" / "audit.jsonl"
state = {"down": False}


def write(record: dict) -> None:
    if state["down"]:
        raise ConnectionError("audit store unreachable")
    PATH.parent.mkdir(exist_ok=True)
    with PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")


def clear() -> None:
    PATH.unlink(missing_ok=True)


def show() -> None:
    print(f"Audit log ({PATH.name}):")
    for line in PATH.read_text().splitlines() if PATH.exists() else []:
        print(f"  {line}")
