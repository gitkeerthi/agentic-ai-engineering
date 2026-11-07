"""Chapter 10 demo: a program reads the agent's text answer with Chapter 6's extractor.

The extractor finds each labeled line and every record ID in the answer. Then the program asks what
Chapter 9's refiling gate would need to know: which document to refile, against which case.
"""

import asyncio
import re
import sys

from investigate import TASK, investigator, show

IDS = r"\b(?:SH|RTM|DOC)-\d+\b"


def line(label: str, answer: str) -> str:  # Chapter 6's extractor, unchanged
    match = re.search(rf"^\W*(?:\w+ )?{label}[^:]*:\W*(.+)$", answer, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip(" *") if match else "(not stated)"


task = sys.argv[1] if len(sys.argv) > 1 else TASK
result = asyncio.run(investigator().run(task))
show(result)
answer = result.messages[-1].text

found = {label: line(label, answer) for label in ("Cause", "Evidence", "Recommended action")}
ids = sorted(set(re.findall(IDS, answer)))
print("\n=== What the program extracted")
for label, value in found.items():
    print(f"{label}: {value}")
print(f"IDs: {ids}")

documents = [i for i in ids if i.startswith("DOC-")]
cases = [i for i in ids if i.startswith("RTM-")]
missing = [label for label, value in found.items() if value == "(not stated)"]
print(f"\nDocument to refile: {documents[0] if len(documents) == 1 else 'unclear, ' + str(documents)}")
print(f"Case to refile it against: {cases[0] if len(cases) == 1 else 'unclear, ' + str(cases)}")
print(f"Outcome: {'missing ' + ', '.join(missing) if missing else 'all labels found'}; "
      f"{len(documents)} DOC ID(s), {len(cases)} RTM ID(s)")
