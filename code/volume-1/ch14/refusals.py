"""Chapter 14 experiment, no model: every report the framework refused in a store's
evidence, and why. A refused report is a model call spent for nothing.

    uv run python ch14/refusals.py STORE

The framework sends the model "Error: Argument parsing failed." for two different
problems: arguments that aren't JSON at all, and JSON the Finding contract refuses.
"""

import json
import sys
from collections import Counter

from pydantic import ValidationError

from contracts import Finding
from show import HERE, load

REFUSED = "Error: Argument parsing failed."

kinds, runs = Counter(), Counter()
for evidence in load(HERE / "store" / sys.argv[1], "evidence"):
    messages = (evidence["response"] or {}).get("messages", [])
    contents = [c for m in messages for c in m["contents"]]
    refused = {c["call_id"] for c in contents if c.get("result") == REFUSED}
    for call in (c for c in contents if c["type"] == "function_call"):
        if call["call_id"] not in refused:
            continue
        try:
            Finding.model_validate(json.loads(call["arguments"]))
            kind = "accepted on a second look"
        except json.JSONDecodeError:
            kind = "not JSON"
        except ValidationError as error:
            kind = f"contract: {error.errors()[0]['msg']}"
        kinds[kind] += 1
        runs[evidence["trace_id"]] += 1

print(f"{sum(kinds.values())} refused reports in {len(runs)} runs")
for kind, n in kinds.most_common():
    print(f"  {n}  {kind}")
