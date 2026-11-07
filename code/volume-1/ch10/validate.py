"""Chapter 10 demo: each layer of the check on one reply at a time. No model call.

Most replies are written by hand to fail one layer each. Two are real, copied from earlier runs: a reply from
json_mode.py --prompt-only on SH-5120 (its first sentence cut) and a finding that tool_output.py reported for SH-5120.
"""

import json

from cobalt import CUSTOMS_CASES, DOCUMENTS, SHIPMENTS
from contracts import check, record_problems

PROSE = "The picture is clear: the shipment is moving normally with no customs case and no hold \u2014 nothing in the records shows a delay."
PROSE_FINDING = {"shipment_id": "SH-5120", "status": "nothing_wrong", "cause": None, "evidence": [
    {"record_id": "SH-5120", "fact": "The shipment is in transit in Singapore and due next Wednesday, with no customs case linked and no hold shown."},
    {"record_id": "SH-5120", "fact": "No customs case exists for this shipment, so no customs hold can be blocking it at this point."}],
    "recommended_action": None, "refiling": None}

REAL_FINDING = {
    "shipment_id": "SH-5120",
    "status": "cause_found",
    "cause": "SH-5120 has no customs case at all, so its documents were uploaded but never filed against a case and no customs declaration exists — the shipment is in transit to Singapore without a customs entry, which will block clearance before its Wednesday due date.",
    "evidence": [
        {
            "record_id": "SH-5120",
            "fact": "Status is in transit in Singapore, due next Wednesday, with contents 'valve assemblies' and customs_case: null."
        },
        {
            "record_id": "DOC-6102",
            "fact": "Commercial invoice is on file but filed_against_customs_case is null."
        },
        {
            "record_id": "DOC-6103",
            "fact": "Bill of lading is on file but filed_against_customs_case is null."
        },
        {
            "record_id": "DOC-6104",
            "fact": "Packing list is on file but filed_against_customs_case is null."
        }
    ],
    "recommended_action": "Open a customs case for SH-5120 and file DOC-6102, DOC-6103 and DOC-6104 against it, then submit the customs declaration (and obtain a certificate of origin, which has no record on file) before the Wednesday due date.",
    "refiling": None
}

VALID = {
    "shipment_id": "SH-4471", "status": "cause_found",
    "cause": "The commercial invoice was filed against another shipment's customs case.",
    "evidence": [{"record_id": "DOC-5531", "fact": "The invoice is filed against RTM-88124."}],
    "recommended_action": "Refile DOC-5531 against RTM-88213.",
    "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"},
}

REPLIES = {
    "a trailing comma": '{"shipment_id": "SH-4471", "status": "cause_found",}',
    "a sentence before the JSON (real, shortened)": PROSE + "\n\n" + json.dumps(PROSE_FINDING),
    "a missing field": json.dumps({k: v for k, v in VALID.items() if k != "cause"}),
    "a status the contract doesn't have": json.dumps({**VALID, "status": "found"}),
    "a malformed document ID": json.dumps({**VALID, "refiling": {"document_id": "5531", "customs_case": "RTM-88213"}}),
    "nothing wrong, but a refiling": json.dumps({**VALID, "status": "nothing_wrong", "cause": None}),
    "refiling against the wrong case": json.dumps({**VALID, "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88124"}}),
    "a cause for a shipment that isn't held (real)": json.dumps(REAL_FINDING),
    "the valid finding": json.dumps(VALID),
}

for label, reply in REPLIES.items():
    finding, verdict = check(reply)
    problems = record_problems(finding, SHIPMENTS, CUSTOMS_CASES, DOCUMENTS) if finding else []
    print(f"{label}:\n   {verdict}" + "".join(f"\n   record check: {p}" for p in problems))
