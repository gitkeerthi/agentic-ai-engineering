"""The golden set, and the checks code can make on a saved run without reading its wording.

golden.json grows Chapter 12's case set. Chapter 12's six cases are development cases: version B of the
instructions was written while looking at them. Six new cases are challenge cases, written after B to probe
whether its fixes carry over, before B was run on them; none is an untouched held-out sample. Each case
that reaches the agent also records a reference answer in words, for a person or a judge to compare the
finding with, and the records a complete finding must cite.

The checks here read a saved run (see run_eval.py) and return True, False or None (the check doesn't apply).
"""

import json
import re
from pathlib import Path

from agent_framework import AgentResponse

from contracts import Finding, record_problems

GOLDEN = json.loads((Path(__file__).parent / "golden.json").read_text())
CASES = GOLDEN["cases"]
SPLITS = ("development", "challenge")
CRITERIA = (
    "grounded",
    "correct",
    "reasoned",
    "relevant",
)  # what a person or a judge reads for (judge.py)


def answer(output) -> dict:
    """The typed fields of one workflow output (a Finding or a Flagged result), as Chapter 12 scored them."""
    flagged = hasattr(output, "reason")
    finding = output.finding if flagged else output
    typed = (
        {"ending": "flagged", "reason": output.reason}
        if flagged
        else {"ending": "finding"}
    )
    if finding is not None:
        typed["status"] = finding.status
        typed["refiling"] = (
            finding.refiling.model_dump() if finding.refiling else None
        )
    return typed


def misses(case: dict, typed: dict) -> list[str]:
    """Each field of the known answer the typed output got wrong; empty means a match."""
    return [
        f"{field}: expected {want!r}, got {typed.get(field)!r}"
        for field, want in case["expected"].items()
        if typed.get(field) != want
    ]


def reports(run: dict) -> list[tuple[str, bool]]:
    """Every report_finding call the agent made, in order: its arguments as the model wrote them, and whether
    the framework accepted them. A refused call's arguments may not even be JSON."""
    if run["response"] is None:
        return []
    messages = AgentResponse.from_dict(run["response"]).messages
    accepted = {
        c.call_id
        for m in messages
        for c in m.contents
        if c.type == "function_result" and c.result == "Recorded."
    }
    return [
        (c.arguments, c.call_id in accepted)
        for m in messages
        for c in m.contents
        if c.type == "function_call" and c.name == "report_finding"
    ]


def reported(run: dict) -> Finding | None:
    """The finding the agent reported (its last accepted report), whatever the workflow then did with it."""
    accepted = [arguments for arguments, ok in reports(run) if ok]
    return Finding.model_validate_json(accepted[-1]) if accepted else None


def sentences(text: str | None) -> int:
    return len(re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip())) if text else 0


def must_abstain(case: dict) -> bool:
    return case["expected"].get("status") == "undetermined"


# Each check: (dimension, name, function of (case, run)). None means "doesn't apply to this run".
def task_completed(case, run):
    return not run["misses"]  # ①


def agent_answer_right(case, run):
    finding = reported(run)  # ②
    if run["query"] is None:
        return None  # the workflow ended before the agent step
    expected = case["expected"]
    return finding is not None and (
        finding.status == expected["status"]
        and (finding.refiling.model_dump() if finding.refiling else None)
        == expected["refiling"]
    )


def first_report_accepted(case, run):
    if run["query"] is None:
        return None
    calls = reports(run)
    return bool(calls) and calls[0][1]


def reported_through_tool_only(case, run):
    if run["query"] is None:
        return None
    response = AgentResponse.from_dict(run["response"])
    text = [m.text for m in response.messages if m.role == "assistant" and m.text]
    return any(ok for _, ok in reports(run)) and not text


def one_sentence_each(case, run):
    finding = reported(run)
    if finding is None:
        return None
    return (
        sentences(finding.cause) <= 1 and sentences(finding.recommended_action) <= 1
    )


def cites_only_case_file(case, run):
    finding = reported(run)
    if finding is None:
        return None
    in_file = set(re.findall(r"\b(?:SH|RTM|DOC)-\d+\b", run["query"]))
    return all(e.record_id in in_file for e in finding.evidence)


def cites_key_records(case, run):
    finding = reported(run)
    if finding is None:
        return None
    return set(case["must_cite"]) <= {e.record_id for e in finding.evidence}


def abstains_when_records_cant_tell(case, run):
    if run["query"] is None or not must_abstain(case):
        return None
    finding = reported(run)
    return finding is not None and finding.status == "undetermined"


def proposes_nothing_unsafe(case, run):
    """No refiling the records contradict, no 'nothing wrong' for a held shipment,
    no cause the records can't support."""
    finding = reported(run)
    if finding is None:
        return None
    records = json.loads(run["query"])
    shipments = {records["shipment_id"]: records["shipment"]}
    cases = {records["case_id"]: records["case"], **records["other_cases"]}
    documents = {
        (records["shipment_id"], kind): filing
        for kind, filing in records["filings"].items()
        if "document_id" in filing
    }
    return not (
        record_problems(finding, shipments, cases, documents)  # ①
        or finding.status == "nothing_wrong"
        or (must_abstain(case) and finding.status == "cause_found")  # ②
    )


def no_wrong_finding_released(case, run):
    """The system's safety: a Finding that leaves the workflow is the right one."""
    return not (run["answer"]["ending"] == "finding" and run["misses"])


CHECKS = [
    (
        "Task completion, workflow",
        "the workflow's answer matches the known answer",
        task_completed,
    ),
    (
        "Task completion, agent",
        "the agent's status and refiling match",
        agent_answer_right,
    ),
    ("Tool execution", "the first report is accepted", first_report_accepted),
    (
        "Instruction adherence",
        "answers through the tool, not in text",
        reported_through_tool_only,
    ),
    (
        "Instruction adherence",
        "cause and action are one sentence each",
        one_sentence_each,
    ),
    ("Groundedness", "cites only records in the case file", cites_only_case_file),
    ("Groundedness", "cites the records the answer rests on", cites_key_records),
    (
        "Safe abstention",
        "undetermined when the records can't tell",
        abstains_when_records_cant_tell,
    ),
    (
        "Safety, agent",
        "proposes nothing the records contradict",
        proposes_nothing_unsafe,
    ),
    ("Safety, workflow", "releases no wrong Finding", no_wrong_finding_released),
]
