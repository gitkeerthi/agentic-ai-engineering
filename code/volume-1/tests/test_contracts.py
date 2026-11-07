"""The finding contract's cross-field rules: what the framework refuses before the workflow sees a report."""

import pytest
from pydantic import ValidationError

from cobalt_exceptions.domain.contracts import Finding, InvestigationRequest
from findings import misfiled_invoice, undetermined


def test_a_cause_needs_a_fault():
    with pytest.raises(ValidationError, match="needs a cause, a fault"):
        Finding.model_validate(misfiled_invoice(fault=None))


def test_only_a_cause_has_a_fault():
    with pytest.raises(ValidationError, match="can't come with a cause, a fault"):
        Finding.model_validate(
            undetermined("SH-4588", "RTM-88377")
            | {"fault": misfiled_invoice()["fault"]}
        )


def test_only_undetermined_has_an_open_question():
    with pytest.raises(ValidationError, match="only an undetermined finding"):
        Finding.model_validate(misfiled_invoice(open_question="Is it signed?"))


def test_message_ids_are_valid_evidence():
    finding = Finding.model_validate(
        misfiled_invoice(evidence=[{"record_id": "MSG-7001", "fact": "hold notice"}])
    )
    assert finding.evidence[0].record_id == "MSG-7001"


def test_a_request_names_a_shipment():
    with pytest.raises(ValidationError):
        InvestigationRequest(shipment_id="4471", requested_by="analyst-017")
