"""Chapter 13's golden set (golden.json, unchanged), and the comparison of a run's typed output with a case's
known answer. Production runs have no known answer; the lab uses one to say which runs were right.
"""

import json
from pathlib import Path

GOLDEN = json.loads((Path(__file__).parent / "golden.json").read_text())
CASES = GOLDEN["cases"]
BY_SHIPMENT = {case["shipment_id"]: case for case in CASES}


def answer(output: dict | None) -> dict:
    """The typed fields of one saved output (a Finding, or a Flagged result), as Chapter 12 scored them."""
    if output is None:
        return {"ending": "failed"}
    flagged = "reason" in output
    finding = output["finding"] if flagged else output
    typed = (
        {"ending": "flagged", "reason": output["reason"]}
        if flagged
        else {"ending": "finding"}
    )
    if finding is not None:
        typed["status"] = finding["status"]
        typed["refiling"] = finding["refiling"]
    return typed


def right(shipment_id: str, output: dict | None) -> bool:
    """Does the typed output match every field of the case's known answer?"""
    typed = answer(output)
    return all(
        typed.get(field) == want
        for field, want in BY_SHIPMENT[shipment_id]["expected"].items()
    )
