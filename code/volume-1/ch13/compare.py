"""Chapter 13 demo, no model: how sure can we be that one version is better than the other?

    uv run python ch13/compare.py [A B]

Reads the saved runs of two versions and counts, for the cases that reach the agent, the runs whose typed
answer matches the known answer. Prints each version's pass rate with a 95% Wilson interval, per case and per
split; the paired difference (second minus first) case by case, and its mean with a standard error clustered
by case, as Miller recommends: a 95% interval from the normal distribution, and one with the usual small-sample
correction (a t distribution with one degree of freedom fewer than the cases). With four or five cases neither
is reliable. Then the wrong Findings each version released, with Fisher's exact test, and a rough count of
runs per version to detect a drop from the first version's pass rate.
"""

import json
import sys
from pathlib import Path
from statistics import mean

from scipy.stats import binomtest, fisher_exact, norm, t

from golden import CASES, SPLITS

first, second = sys.argv[1:3] if len(sys.argv) > 2 else ("A", "B")
here = Path(__file__).parent


def load(version: str, agent_cases_only: bool = True) -> list[dict]:
    lines = (here / "results" / f"{version}.jsonl").read_text().splitlines()
    saved = list(map(json.loads, lines))
    return (
        [r for r in saved if r["query"] is not None] if agent_cases_only else saved
    )


def rate(runs: list[dict]) -> str:
    passed = sum(not r["misses"] for r in runs)
    low, high = binomtest(passed, len(runs)).proportion_ci(method="wilson")  # ①
    return (
        f"{passed:>2}/{len(runs):<3} {passed / len(runs):>4.0%}  "
        f"[{low:.0%}, {high:.0%}]"
    )


runs = {first: load(first), second: load(second)}
agent_cases = [
    c
    for c in CASES
    if any(r["shipment_id"] == c["shipment_id"] for r in runs[first])
]

print(
    f"{'Case':<9}{'split':<13}{first + ', 95% interval':>28}{second + ', 95% interval':>28}"
)
for case in agent_cases:
    cells = [
        rate([r for r in runs[v] if r["shipment_id"] == case["shipment_id"]])
        for v in runs
    ]
    print(f"{case['shipment_id']:<9}{case['split']:<13}{cells[0]:>28}{cells[1]:>28}")
for split in SPLITS:
    cells = [rate([r for r in runs[v] if r["split"] == split]) for v in runs]
    print(f"{'All':<9}{split:<13}{cells[0]:>28}{cells[1]:>28}")

print(f"\nPaired difference, {second} minus {first}, case by case:")
for split in SPLITS:
    differences, sizes = [], []
    for case in (c for c in agent_cases if c["split"] == split):
        counts = []
        for v in (first, second):
            mine = [r for r in runs[v] if r["shipment_id"] == case["shipment_id"]]
            counts.append((sum(not r["misses"] for r in mine), len(mine)))
        (pass_a, n), (pass_b, n_b) = counts
        assert n == n_b, "both versions need the same runs per case"
        differences.append(pass_b / n - pass_a / n)
        sizes.append(n)
        print(f"  {case['shipment_id']}  {split:<12} {differences[-1]:+.0%}")
    k, runs_in_split = len(differences), sum(sizes)
    average = sum(n * d for n, d in zip(sizes, differences)) / runs_in_split
    clustered = (  # ①
        sum((n * (d - average)) ** 2 for n, d in zip(sizes, differences)) ** 0.5
        / runs_in_split
    )
    normal = norm.ppf(0.975) * clustered
    corrected = t.ppf(0.975, k - 1) * clustered * (k / (k - 1)) ** 0.5  # ②
    print(f"  {split}, {k} cases, {runs_in_split} runs a version: {average:+.0%}")
    print(
        f"    clustered by case: normal [{average - normal:+.0%}, "
        f"{average + normal:+.0%}]; small-sample [{average - corrected:+.0%}, "
        f"{average + corrected:+.0%}]"
    )


released = {
    v: sum(
        r["answer"]["ending"] == "finding" and bool(r["misses"])
        for r in load(v, agent_cases_only=False)
    )
    for v in (first, second)
}
total = len(load(first, agent_cases_only=False))
_, p_value = fisher_exact(
    [
        [released[first], total - released[first]],
        [released[second], total - released[second]],
    ]
)
print(
    f"\nWrong Findings released: {first} {released[first]} of {total}, "
    f"{second} {released[second]} of {total}; Fisher's exact test p = {p_value:.2f}"
)

baseline = mean(not r["misses"] for r in runs[first])
print(
    f"\nRuns per version to detect a drop from {first}'s {baseline:.0%} (both splits): "
    "two proportions,\n  runs as independent tries, two-sided 95%, 80% power:"
)
for difference in (0.30, 0.20, 0.10, 0.05):
    other = baseline - difference
    variance = baseline * (1 - baseline) + other * (1 - other)
    needed = (norm.ppf(0.975) + norm.ppf(0.80)) ** 2 * variance / difference**2
    print(f"  {difference:.0%} points: about {needed:,.0f} runs per version")
