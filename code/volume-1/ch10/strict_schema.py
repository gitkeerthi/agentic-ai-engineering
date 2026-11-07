"""Chapter 10 demo: does the provider hold a tool call to its schema when the request says otherwise?

First a one-field tool whose status must be "open" or "closed", asked for "pending": without strict mode, with
it, and with the field one object down. Then three requests that contradict the Finding schema: a status the
enum doesn't allow plus a field the schema doesn't have; a shipment ID that breaks its pattern; and a document
ID that breaks its pattern inside the nested refiling object. Each starts from a valid finding. The model is
made to call the tool, under three definitions of it, twenty calls each by default, and the arguments are
checked against the exact schema sent. No agent and no framework: each call is one request to the beta endpoint.
"""

import json
import sys
from collections import Counter

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from agentlab.llm import chat
from contracts import Finding
from strict import closed, inlined

CONTEXT = "SH-4471 is held: invoice DOC-5531 was filed against customs case RTM-88124 instead of RTM-88213.\n"
ASK = "Report the finding with exactly these arguments and no others:\n"
GOOD = {"shipment_id": "SH-4471", "status": "cause_found", "cause": "The invoice was filed against RTM-88124.",
        "evidence": [{"record_id": "DOC-5531", "fact": "Filed against RTM-88124."}],
        "recommended_action": "Refile the invoice.", "refiling": {"document_id": "DOC-5531", "customs_case": "RTM-88213"}}
REQUESTS = {  # ①
    "a status outside the enum, and an extra field":
        {**GOOD, "status": "found",
         "root_cause": "The invoice was filed against RTM-88124."},
    "a shipment ID that breaks its pattern": {**GOOD, "shipment_id": "4471"},
    "a document ID that breaks its pattern, inside refiling":
        {**GOOD, "refiling": {"document_id": "5531", "customs_case": "RTM-88213"}},
}

STATUS = {"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "closed"]}},
          "required": ["status"], "additionalProperties": False}
ONE_FIELD = {
    "not strict": (STATUS, False, {"status": "pending"}),
    "strict": (STATUS, True, {"status": "pending"}),
    "strict, one object down": ({"type": "object", "properties": {"case": STATUS}, "required": ["case"],
                                 "additionalProperties": False}, True, {"case": {"status": "pending"}}),
}

finding = Finding.model_json_schema()
DEFINITIONS = {  # ②
    "not strict, as Pydantic writes it": (finding, False),
    "strict, as Pydantic writes it": (closed(finding), True),
    "strict, inlined": (closed(inlined(finding)), True),
}


def against(parameters: dict):
    """An outcome function: do the arguments match the exact schema that was sent? If not, the first reason."""
    validator = Draft202012Validator(parameters)

    def outcome(arguments: str) -> str:
        error = best_match(validator.iter_errors(json.loads(arguments)))
        return "matches the schema" if error is None else f"doesn't match: {error.message[:90]}"
    return outcome


def tally(name: str, parameters: dict, strict: bool, content: str, outcome) -> None:
    """Make the model call report `calls` times under one tool definition, and count what came back."""
    tool = {"type": "function", "function": {"name": "report", "description": "Report.",
                                             "parameters": parameters, **({"strict": True} if strict else {})}}
    outcomes = Counter()
    for _ in range(calls):
        try:
            response = chat([{"role": "user", "content": content}], beta=True, tools=[tool],
                            tool_choice={"type": "function", "function": {"name": "report"}})
            outcomes[outcome(response.choices[0].message.tool_calls[0].function.arguments)] += 1
        except Exception as error:
            outcomes[f"request refused: {str(error)[:100]}"] += 1
    print(f"{name}:")
    for result, count in outcomes.most_common():
        print(f"   {count} of {calls}: {result}")


calls = int(sys.argv[1]) if len(sys.argv) > 1 else 20
print('=== A one-field tool, asked for "pending"')
for name, (parameters, strict, request) in ONE_FIELD.items():
    tally(name, parameters, strict, f"Call report with exactly {json.dumps(request)}.", lambda arguments: arguments)
for request_name, request in REQUESTS.items():
    print(f"=== The Finding, asked for {request_name}")
    for name, (parameters, strict) in DEFINITIONS.items():
        tally(name, parameters, strict, CONTEXT + ASK + json.dumps(request), against(parameters))
