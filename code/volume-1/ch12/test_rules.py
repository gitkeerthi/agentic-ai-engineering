"""Chapter 12 unit tests: Cobalt's rules about a finding, each tested on its own, with no workflow and no model.

uv run pytest ch12/test_rules.py -v
"""

import pytest
from pydantic import ValidationError

import cobalt
from contracts import Finding, record_problems
from replies import SUPPORTED
from steps import covered, no_hold


def finding(**changes) -> Finding:
    return Finding.model_validate({**SUPPORTED, **changes})  # ①


def problems(f: Finding) -> list[str]:
    return record_problems(
        f, cobalt.SHIPMENTS, cobalt.CUSTOMS_CASES, cobalt.DOCUMENTS
    )


@pytest.mark.parametrize(
    "changes, phrase",
    [
        ({"refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88124"}},
         "refiling targets RTM-88124"),
        ({"refiling": {"document_id": "DOC-5601", "customs_case": "RTM-88213"}},
         "DOC-5601 is not one of SH-4471's documents"),
        ({"shipment_id": "SH-5120", "refiling": None},
         "SH-5120 is in transit"),
        ({"shipment_id": "SH-9999", "refiling": None},
         "no shipment SH-9999"),
    ],
    ids=["wrong case", "another shipment's document", "not held", "unknown"],
)  # fmt: skip
def test_record_problems_names_what_the_records_contradict(changes, phrase):
    [problem] = problems(finding(**changes))  # ②
    assert phrase in problem


def test_record_problems_passes_a_supported_finding():
    assert problems(finding()) == []  # ③


@pytest.mark.parametrize(
    "case, expected",
    [
        ({"status": "on hold",
          "hold_reason": "required document not received"}, True),
        ({"status": "on hold", "hold_reason": "physical inspection"}, False),
        ({"status": "on hold", "hold_reason": None}, False),
        ({"status": "cleared", "hold_reason": None}, False),
    ],
    ids=["document hold", "inspection", "no reason", "cleared"],
)  # fmt: skip
def test_covered_only_document_holds(case, expected):
    assert covered(case) is expected


@pytest.mark.parametrize(
    "changes, phrase",
    [
        ({"evidence": []}, "cause_found needs a cause"),
        ({"status": "nothing_wrong", "refiling": None}, "can't come with a cause"),
        ({"evidence": [{"record_id": "DOC-55", "fact": "Short ID."}]},
         "String should match"),
    ],
    ids=["cause without evidence", "nothing wrong with a cause", "malformed ID"],
)  # fmt: skip
def test_finding_contract_refuses(changes, phrase):
    with pytest.raises(ValidationError, match=phrase):
        finding(**changes)


def test_no_hold_cites_the_shipment_and_its_case():
    shipment = cobalt.shipment_status("SH-4471") | {"status": "delivered"}
    result = no_hold("SH-4471", shipment, "RTM-88213")
    assert result.status == "nothing_wrong"
    assert [e.record_id for e in result.evidence] == ["SH-4471", "RTM-88213"]
