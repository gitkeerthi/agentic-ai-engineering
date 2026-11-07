"""Cobalt's procedure for a customs hold, as rules: where each read can end the investigation, and
what a finding must agree with before anyone sees it. No framework code: the workflow's steps
call these functions, and the tests call them directly.
"""

import json
import re
from dataclasses import asdict

from .contracts import CaseFile, Evidence, Finding, Flagged

# The hold reasons this procedure covers. Customs gives the reason as a fixed value,
# so this is a rule, not a reading of free text.
DOCUMENT_HOLDS = {"required document not received"}


def no_hold(shipment_id: str, shipment: dict, case_id: str | None = None) -> Finding:
    """Cobalt's rule: not held, and no customs case on hold, means nothing holds it."""
    fact = f"{shipment['status']} in {shipment['location']}, due {shipment['due']}"
    evidence = [
        Evidence(
            record_id=shipment_id,
            fact=fact if case_id else f"{fact}, no customs case",
        )
    ]
    if case_id:
        evidence.append(
            Evidence(record_id=case_id, fact="the customs case isn't on hold")
        )
    return Finding(
        shipment_id=shipment_id,
        status="nothing_wrong",
        cause=None,
        fault=None,
        evidence=evidence,
        recommended_action=None,
        refiling=None,
    )


def after_shipment(shipment_id: str, shipment: dict) -> Finding | Flagged | None:
    """The ending the shipment record decides, or None to read its customs case next."""
    if "error" in shipment:
        return Flagged(
            shipment_id=shipment_id,
            reason="unknown_shipment",
            finding=None,
            problems=[shipment["error"]],
        )
    if shipment["customs_case"] is None and shipment["status"] != "held":
        return no_hold(shipment_id, shipment)
    if shipment["customs_case"] is None:
        problem = (
            f"{shipment['status']} with no customs case: outside this procedure"
        )
        return Flagged(
            shipment_id=shipment_id,
            reason="outside_procedure",
            finding=None,
            problems=[problem],
        )
    return None


def after_case(
    shipment_id: str,
    shipment: dict,
    case_id: str,
    case: dict,
    required: list[dict] | None,
) -> Finding | Flagged | None:
    """The ending the customs case decides, or None to search for its documents next."""
    if "error" in case:
        return Flagged(
            shipment_id=shipment_id,
            reason="records_missing",
            finding=None,
            problems=[case["error"]],
        )
    if shipment["status"] != "held" and case["status"] != "on hold":
        return no_hold(shipment_id, shipment, case_id)
    if not (case["status"] == "on hold" and case["hold_reason"] in DOCUMENT_HOLDS):
        if case["status"] == "on hold":
            why = f"customs case {case_id} is on hold for {case['hold_reason'] or 'no recorded reason'}"
        else:
            why = f"held, but customs case {case_id} is {case['status']}"
        return Flagged(
            shipment_id=shipment_id,
            reason="outside_procedure",
            finding=None,
            problems=[f"{why}: outside this procedure"],
        )
    if required is None:
        problem = f"customs case {case_id} has no list of required documents"
        return Flagged(
            shipment_id=shipment_id,
            reason="records_missing",
            finding=None,
            problems=[problem],
        )
    return None


def ids_in(case_file: CaseFile) -> set[str]:
    """Every record ID the case file holds."""
    return set(re.findall(r"\b(?:SH|RTM|DOC)-\d+\b", json.dumps(asdict(case_file))))


def fault_problems(
    finding: Finding, case_file: CaseFile, retrieved: dict[str, dict]
) -> list[str]:
    """Does the case file, or a message the agent retrieved and cited, show the
    fault the finding names?"""
    fault = finding.fault
    if fault is None:
        return []
    item = next(
        (r for r in case_file.required if r["document"] == fault.document), None
    )
    if item is None:
        return [f"{case_file.case_id} doesn't require a {fault.document}"]
    if item["received"]:
        return [
            f"customs has received the {fault.document}, "
            "so it isn't what holds the shipment"
        ]
    filing = case_file.filings.get(fault.document, {})
    document_id = filing.get("document_id")
    filed_against = filing.get("filed_against_customs_case")
    if fault.problem == "not_uploaded":  # ①
        return (
            [f"the store has the {fault.document} as {document_id}"]
            if document_id
            else []
        )
    if fault.problem == "filed_against_another_case":  # ②
        if filed_against in (None, case_file.case_id):
            return [f"the {fault.document} isn't filed against another case"]
        wanted = (document_id, case_file.case_id)
        got = (
            (finding.refiling.document_id, finding.refiling.customs_case)
            if finding.refiling
            else None
        )
        return (
            []
            if got == wanted
            else [f"the fix is to refile {wanted[0]} against {wanted[1]}"]
        )
    cited = {e.record_id for e in finding.evidence}  # ③ rejected_by_customs
    rejections = [
        m
        for m in retrieved.values()
        if m["message_id"] in cited
        and m["sender"] == "customs"
        and m["kind"] == "rejection"
        and m.get("document_id") == document_id
    ]
    if not rejections:
        return [
            f"no customs rejection of the {fault.document} "
            "is cited from the messages retrieved"
        ]
    return []


def record_problems(finding: Finding, case_file: CaseFile) -> list[str]:
    """Claims about the shipment, its case or a refiling that the case file contradicts."""
    problems = []
    if finding.refiling:
        if finding.refiling.customs_case != case_file.case_id:
            problems.append(
                f"refiling targets {finding.refiling.customs_case}, "
                f"but {finding.shipment_id}'s case is {case_file.case_id}"
            )
        owned = {f.get("document_id") for f in case_file.filings.values()}
        if finding.refiling.document_id not in owned:
            problems.append(
                f"{finding.refiling.document_id} is not one of {finding.shipment_id}'s documents"
            )
        if finding.fault and finding.fault.problem != "filed_against_another_case":
            problems.append(
                "a refiling fixes only a document filed against another case"
            )
    return problems


def check_finding(
    finding: Finding | None,
    case_file: CaseFile,
    retrieved: dict[str, dict],
    note: str = "",
) -> Finding | Flagged:
    """The finding, if every check passes; otherwise a flag for a person, with every problem found."""
    shipment_id = case_file.shipment_id
    if finding is None:
        return Flagged(
            shipment_id=shipment_id,
            reason="no_usable_finding",
            finding=None,
            problems=[note],
        )
    known = ids_in(case_file) | set(retrieved)
    problems = [
        f"{e.record_id} is cited but isn't in the case file or the messages retrieved"
        for e in finding.evidence
        if e.record_id not in known  # provenance: only what this run actually saw
    ]
    if finding.shipment_id != shipment_id:
        problems.append(
            f"the finding is about {finding.shipment_id}, not {shipment_id}"
        )
    if finding.status == "undetermined":
        problems.append("the agent couldn't tell from the records and messages")
    if finding.status == "nothing_wrong":
        problems.append(
            "nothing_wrong, but the shipment or its customs case is on hold"
        )
    problems += record_problems(finding, case_file)
    problems += fault_problems(finding, case_file, retrieved)
    if not problems:
        return finding
    reason = (
        "finding_problems"
        if finding.status == "cause_found"
        else "no_usable_finding"
    )
    return Flagged(
        shipment_id=shipment_id, reason=reason, finding=finding, problems=problems
    )
