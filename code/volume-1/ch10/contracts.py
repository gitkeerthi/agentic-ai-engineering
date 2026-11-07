"""Chapter 10's contract for an investigation finding: what the refiling gate, the case set and a person read."""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator


class Evidence(BaseModel):
    record_id: str = Field(pattern=r"^(SH-\d{4}|RTM-\d{5}|DOC-\d{4})$",
                           description="ID of the record that shows the fact")
    fact: str = Field(description="What that record shows, in one sentence")


class Refiling(BaseModel):
    document_id: str = Field(
        pattern=r"^DOC-\d{4}$", description="The misfiled document")
    customs_case: str = Field(
        pattern=r"^RTM-\d{5}$",
        description="The customs case it should be filed against")


class Finding(BaseModel):
    shipment_id: str = Field(pattern=r"^SH-\d{4}$")
    status: Literal["cause_found", "nothing_wrong", "undetermined"] = Field(  # ①
        description="cause_found: the records show what is delaying it; "
        "nothing_wrong: the records show no problem; "
        "undetermined: the tools could not tell")
    cause: str | None = Field(  # ②
        description="One sentence; null unless status is cause_found")
    evidence: list[Evidence] = Field(
        description="The facts that support the status, one per record")
    recommended_action: str | None = Field(
        description="One sentence for a person; null if nothing needs doing")
    refiling: Refiling | None = Field(
        description="Set only when the fix is to refile a misfiled document")  # ③

    @model_validator(mode="after")
    def parts_agree(self) -> "Finding":  # ④
        if self.status == "cause_found" and not (self.cause and self.evidence):
            raise ValueError(
                "cause_found needs a cause and at least one piece of evidence")
        if self.status != "cause_found" and (self.cause or self.refiling):
            raise ValueError(
                f"status {self.status} can't come with a cause or a refiling")
        return self


def check(text: str) -> tuple[Finding | None, str]:
    """Parse and validate one reply. Returns the Finding, or None and the
    first thing wrong with it."""
    if not text.strip():
        return None, "blank reply"  # ①
    try:
        json.loads(text)
    except json.JSONDecodeError as error:
        return None, f"not JSON: {error.msg}"  # ②
    try:
        return Finding.model_validate_json(text), "valid"
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "Finding"
        return None, f"schema: {where}: {first['msg']}"  # ③


def provenance_problems(finding: Finding, result,
                        reporting_tool: str = "report_finding") -> list[str]:
    """Evidence the run never saw: every cited record must be one a tool looked up and found, or returned."""
    asked = {}  # each lookup's arguments, by call ID
    seen = set()
    for message in result.messages:
        for content in message.contents:
            if (content.type == "function_call"
                    and content.name != reporting_tool):  # ①
                asked[content.call_id] = str(content.arguments)
            elif content.type == "function_result" and content.call_id in asked:
                text = str(content.result)
                if "error" in text.lower() or '"found": false' in text.lower():  # ②
                    continue
                seen.update(re.findall(r"\b(?:SH|RTM|DOC)-\d+\b",
                                       text + asked[content.call_id]))
    return [f"{e.record_id} is cited as evidence but no tool confirmed it"
            for e in finding.evidence if e.record_id not in seen]


def record_problems(finding: Finding, shipments: dict, cases: dict,
                    documents: dict) -> list[str]:
    """Claims the records contradict: Cobalt's rules about what a finding can say."""
    shipment = shipments.get(finding.shipment_id)
    if shipment is None:
        return [f"no shipment {finding.shipment_id}"]
    problems = []
    case = cases.get(shipment["customs_case"] or "")
    if (finding.status == "cause_found" and shipment["status"] != "held"
            and not (case and case["status"] == "on hold")):  # ①
        problems.append(f"cause_found, but {finding.shipment_id} is "
                        f"{shipment['status']} and no customs case holds it")
    if finding.refiling:
        if finding.refiling.customs_case != shipment["customs_case"]:  # ②
            problems.append(f"refiling targets {finding.refiling.customs_case}, "
                            f"but {finding.shipment_id}'s case is "
                            f"{shipment['customs_case']}")
        owned = {d["document_id"] for (s, _), d in documents.items()
                 if s == finding.shipment_id}
        if finding.refiling.document_id not in owned:
            problems.append(f"{finding.refiling.document_id} is not one of "
                            f"{finding.shipment_id}'s documents")
    return problems
