"""The book's first case set: held shipments with known answers, scored from the investigation's typed output.

Each case in cases.json names a shipment and the answer we know is right: the ending (a Finding or a Flagged
result), the finding's status or the flag's reason, and the refiling, if any. Scoring compares those typed
fields and nothing else. The finding's wording is never scored here; Chapter 13 takes up how good it is.
"""

import json
from pathlib import Path

from contracts import Finding
from steps import Flagged

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())


def answer(output: Finding | Flagged) -> dict:
    """The typed fields of one output that a known answer can be compared with."""
    if isinstance(output, Flagged):
        finding = output.finding
        typed = {"ending": "flagged", "reason": output.reason}
    else:
        finding = output
        typed = {"ending": "finding"}
    if finding is not None:
        typed["status"] = finding.status
        typed["refiling"] = (
            finding.refiling.model_dump() if finding.refiling else None
        )
    return typed


def misses(case: dict, output: Finding | Flagged) -> list[str]:
    """Each field of the known answer the output got wrong; empty means a match."""
    got = answer(output)
    return [
        f"{field}: expected {want!r}, got {got.get(field)!r}"
        for field, want in case["expected"].items()
        if got.get(field) != want
    ]
