"""Chapter 14 demo, no model: the metrics a batch left (week.py), read from the last export in the store's
metrics file. The framework's histograms of model-call time and tokens, and our count of investigations by
outcome. Metrics are aggregates: counts, sums and buckets, with no case in them, except the exemplars, which
point from a data point to one trace.

    uv run python ch14/metrics.py STORE
"""

import json
import sys

from show import HERE, role

store = HERE / "store" / sys.argv[1]
last = json.loads(
    (store / "metrics.jsonl").read_text().splitlines()[-1]
)  # cumulative totals since the start
for scope in last["resource_metrics"][0]["scope_metrics"]:
    for metric in scope["metrics"]:
        print(f"{metric['name']} ({metric.get('unit') or 'count'})")
        for point in metric["data"]["data_points"]:
            a = point["attributes"]
            labels = ", ".join(
                f"{k.split('.')[-1]}={role(v) if 'model' in k else v}"
                for k, v in a.items()
                if k
                in (
                    "gen_ai.response.model",
                    "gen_ai.token.type",
                    "outcome",
                    "reason",
                    "agent_framework.function.name",
                )
                and v != ""
            )
            if "sum" in point and "count" in point:  # a histogram
                line = f"count {point['count']}, sum {point['sum']:,.2f}, min {point['min']:,.2f}, max {point['max']:,.2f}"
            else:  # a counter
                line = f"{point['value']}"
            print(f"    {labels or '(all)'}: {line}")
            if point.get("exemplars"):
                exemplar = point["exemplars"][-1]
                print(
                    f"      exemplar: value {exemplar['value']:,.2f} in trace {exemplar['trace_id']:032x}"
                )
