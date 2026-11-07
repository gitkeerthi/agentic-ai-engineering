"""The investigation's contracts: what it is asked, what it gathers, and what it returns.

Chapter 10's finding, with the two fields Chapter 13 recommended: a typed fault, which the
workflow can check against the records, and an open question for a finding that can't say.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, model_validator

RECORD_ID = r"^(SH-\d{4}|RTM-\d{5}|DOC-\d{4}|MSG-\d{4})$"
DocumentType = Literal["bill of lading", "commercial invoice", "packing list"]


class InvestigationRequest(BaseModel):
    """The research objective: which shipment, who asks, and what they want to know."""

    shipment_id: str = Field(pattern=r"^SH-\d{4}$")
    requested_by: str  # the person asking; an identity provider would vouch for it
    objective: str = (
        "Find what is holding this shipment and the action that would release it."
    )


class Evidence(BaseModel):
    record_id: str = Field(
        pattern=RECORD_ID,
        description="ID of the record or message that shows the fact",
    )
    fact: str = Field(description="What that record shows, in one sentence")


class Fault(BaseModel):
    document: DocumentType = Field(description="The required document at fault")
    problem: Literal[
        "not_uploaded", "filed_against_another_case", "rejected_by_customs"
    ] = Field(description="What is wrong with it")


class Refiling(BaseModel):
    document_id: str = Field(
        pattern=r"^DOC-\d{4}$", description="The misfiled document"
    )
    customs_case: str = Field(
        pattern=r"^RTM-\d{5}$",
        description="The customs case it should be filed against",
    )


class Finding(BaseModel):
    shipment_id: str = Field(pattern=r"^SH-\d{4}$")
    status: Literal["cause_found", "nothing_wrong", "undetermined"] = Field(
        description="cause_found: the records or messages show what is holding it; "
        "nothing_wrong: they show nothing holds it; undetermined: they don't show the cause"
    )
    cause: str | None = Field(
        description="One sentence; null unless status is cause_found"
    )
    fault: Fault | None = Field(
        description="The document at fault and its problem; required for cause_found, else null"
    )
    evidence: list[Evidence] = Field(
        description="The facts that support the status, one per record or message"
    )
    recommended_action: str | None = Field(
        description="One sentence for a person; null if nothing needs doing"
    )
    refiling: Refiling | None = Field(
        description="Set only when the fix is to refile a document filed against another case"
    )
    open_question: str | None = Field(
        default=None,
        description="For undetermined only: what a person should find out; else null",
    )

    @model_validator(mode="after")
    def parts_agree(self) -> "Finding":
        if self.status == "cause_found" and not (
            self.cause and self.fault and self.evidence
        ):
            raise ValueError(
                "cause_found needs a cause, a fault "
                "and at least one piece of evidence"
            )
        if self.status != "cause_found" and (
            self.cause or self.fault or self.refiling
        ):
            raise ValueError(
                f"status {self.status} can't come with a cause, a fault or a refiling"
            )
        if self.status != "undetermined" and self.open_question:
            raise ValueError("only an undetermined finding has an open question")
        return self


@dataclass
class CaseFile:
    """What the procedure's reads gathered for one held shipment: the records the agent is shown."""

    shipment_id: str
    shipment: dict
    case_id: str
    case: dict
    required: list[dict]
    filings: dict[str, dict]  # document type -> what the document store has for it
    other_cases: dict[str, dict] = field(
        default_factory=dict
    )  # cases documents are filed against


Reason = Literal[
    "unknown_shipment",  # the requester should check the ID
    "outside_procedure",  # a hold this procedure doesn't cover
    "records_missing",  # a record the procedure needs isn't on file
    "records_unavailable",  # a system stayed unavailable after retries: try again later
    "no_usable_finding",  # couldn't tell, said nothing's wrong, or didn't report
    "finding_problems",  # the finding says something the records don't support
]


class Flagged(BaseModel):
    """A case a person must look at before anything happens, and why."""

    shipment_id: str
    reason: Reason  # what the caller routes on
    finding: Finding | None
    problems: list[str]  # for the person who reads it
