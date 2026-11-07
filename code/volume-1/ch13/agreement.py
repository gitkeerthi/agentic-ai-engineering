"""Chapter 13 demo, no model: how far can the judge be trusted?

    uv run python ch13/agreement.py

Compares saved verdicts (ch13/results/judged-*.jsonl, written by judge.py) with the rubric labels in
labels.json, criterion by criterion: how often the judge agrees; of the findings a person failed, how many the
judge failed too; and of the findings a person passed, how many the judge passed too, each with an exact 95%
interval, since the classes are small. Then how often the same
judge, asked again, gives the same verdict; and which planted errors (seeded.json) each judge caught.
"""

import json
from collections import defaultdict
from pathlib import Path

from scipy.stats import binomtest

from golden import CRITERIA

here = Path(__file__).parent / "results"
labels = {
    (l["version"], l["shipment_id"], l["run"]): l
    for l in json.loads((here.parent / "labels.json").read_text())
}


def share(hits: int, n: int) -> str:
    low, high = binomtest(hits, n).proportion_ci(method="exact")
    return f"{hits:>2} of {n:<2} [{low:.0%}, {high:.0%}]"


def verdicts(*names: str) -> dict:
    """Verdicts by (version, shipment, run), first judging only, from the named files that exist."""
    found = {}
    for name in names:
        path = here / f"judged-{name}.jsonl"
        if not path.exists():
            continue
        version = name.split("-")[0]
        for row in map(json.loads, path.read_text().splitlines()):
            key = (version, row["shipment_id"], row["run"])
            if row["repeat"] == 1 and row["verdict"] and key in labels:
                found[key] = row["verdict"]
    return found


judges = {
    "flash": verdicts("A-flash", "B-flash"),
    "pro": verdicts("A-pro-labeled", "B-pro-labeled"),
}
print(f"Judge against the labels ({len(labels)} labeled findings)")
print(
    f"{'judge':<7}{'criterion':<11}{'agree':>7}   {'failures caught':<21}passes kept"
)
for judge, found in judges.items():
    for criterion in CRITERIA:
        keys = [k for k in labels if k in found]
        agree = sum(found[k][criterion] == labels[k][criterion] for k in keys)
        failed = [k for k in keys if not labels[k][criterion]]
        passed = [k for k in keys if labels[k][criterion]]
        caught = sum(not found[k][criterion] for k in failed)
        kept = sum(found[k][criterion] for k in passed)
        print(
            f"{judge:<7}{criterion:<11}{agree:>4}/{len(keys):<3}  "
            f"{share(caught, len(failed)):<21}{share(kept, len(passed))}"
        )

print("\nThe same judge asked three times (flash, the labeled findings):")
repeats = defaultdict(list)
for name in ("A-flash-labeled-x3", "B-flash-labeled-x3"):
    path = here / f"judged-{name}.jsonl"
    for row in (
        map(json.loads, path.read_text().splitlines()) if path.exists() else []
    ):
        if row["verdict"]:
            repeats[(name[0], row["shipment_id"], row["run"])].append(row["verdict"])
for criterion in CRITERIA:
    steady = sum(len({v[criterion] for v in vs}) == 1 for vs in repeats.values())
    print(
        f"  {criterion:<10} same verdict every time on {steady} of {len(repeats)} findings"
    )

print(
    "\nPlanted errors (seeded.json): did the judge fail the criterion each one plants?"
)
for judge in ("flash", "pro"):
    path = here / f"judged-seeded-{judge}.jsonl"
    if not path.exists():
        continue
    rows = [
        r for r in map(json.loads, path.read_text().splitlines()) if r["repeat"] == 1
    ]
    caught = [r for r in rows if r["verdict"] and not r["verdict"][r["plants"]]]
    missed = [r["run"] for r in rows if r not in caught]
    print(
        f"  {judge}: caught {len(caught)} of {len(rows)}"
        + (f"; missed {', '.join(missed)}" if missed else "")
    )
