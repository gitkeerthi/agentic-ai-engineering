"""The golden set (golden.json), and the comparison of a run's typed output with a case's known answer.

Production runs have no known answer; the evaluation uses one to say which runs were right.
"""

import json
from pathlib import Path

GOLDEN = json.loads((Path(__file__).parent / "golden.json").read_text())
CASES = GOLDEN["cases"]
BY_SHIPMENT = {case["shipment_id"]: case for case in CASES}


def answer(output: dict | None) -> dict:
    """The typed fields of one saved output: a Finding, or a Flagged result with its finding."""
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
        typed |= {
            "status": finding["status"],
            "refiling": finding["refiling"],
            "fault": finding.get("fault"),
        }
    return typed


def right(
    shipment_id: str, output: dict | None, fields: tuple | None = None
) -> bool:
    """Does the typed output match every field of the case's known answer (or only the fields named)?"""
    typed = answer(output)
    expected = BY_SHIPMENT[shipment_id]["expected"]
    return all(
        typed.get(field) == want
        for field, want in expected.items()
        if fields is None or field in fields
    )


def released_wrong(shipment_id: str, output: dict | None) -> bool:
    """A finding left the workflow, and it isn't the right one: the must-pass failure."""
    return answer(output)["ending"] == "finding" and not right(shipment_id, output)
