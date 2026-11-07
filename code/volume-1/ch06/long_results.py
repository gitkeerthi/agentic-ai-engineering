"""Chapter 6 demo: a tool that returns whole documents. How much does a follow-up carry once the session has read
two of them, and what changes when a provider collapses old tool results at the start of each run?

    uv run python ch06/long_results.py
    uv run python ch06/long_results.py --compact
"""

import argparse
import asyncio
from typing import Annotated

from agent_framework import (
    CompactionProvider,
    InMemoryHistoryProvider,
    ToolResultCompactionStrategy,
    included_messages,
    tool,
)

from investigate import FOLLOW_UP, calls, investigator, show

CACHED_PRICE = 1 / 50  # cached input costs a fiftieth of uncached input at the lab model's prices
CHECK_TASK = (
    "Before SH-4471's invoice is refiled, check that its commercial invoice and its packing list "
    "list the same items in the same quantities."
)

# Stand-in line items for SH-4471's industrial pumps: (part, HS customs tariff code, quantity, unit price in EUR,
# net kg each).
PARTS = [
    ("CP-200 centrifugal pump, stainless steel, 7.5 kW", "8413.70", 12, 2450.00, 61.0),
    ("CP-350 centrifugal pump, duplex steel, 15 kW", "8413.70", 6, 4180.00, 118.0),
    ("MP-80 multistage pump, cast iron, 11 kW", "8413.70", 4, 3925.00, 142.5),
    ("SP-40 submersible drainage pump, 2.2 kW", "8413.70", 10, 1310.00, 28.0),
    ("Impeller, CP-200, 210 mm, stainless steel", "8413.91", 24, 312.00, 3.4),
    ("Impeller, CP-350, 265 mm, duplex steel", "8413.91", 12, 486.00, 5.9),
    ("Mechanical seal kit, 35 mm, silicon carbide", "8484.20", 40, 148.50, 0.6),
    ("Mechanical seal kit, 45 mm, silicon carbide", "8484.20", 24, 176.00, 0.8),
    ("Bearing kit, CP series, sealed, pair", "8482.10", 30, 94.00, 1.2),
    ("Shaft sleeve, 35 mm, hardened steel", "8413.91", 20, 61.50, 0.5),
    ("Casing gasket set, CP-200, PTFE", "8484.10", 50, 22.40, 0.2),
    ("Casing gasket set, CP-350, PTFE", "8484.10", 30, 27.80, 0.3),
    ("Flexible motor coupling, 7.5 to 15 kW", "8483.60", 16, 133.00, 2.1),
    ("Baseplate, CP-200, galvanized steel", "7308.90", 12, 214.00, 18.5),
    ("Baseplate, CP-350, galvanized steel", "7308.90", 6, 298.00, 27.0),
    ("Pressure gauge, 0 to 16 bar, glycerine filled", "9026.20", 36, 38.90, 0.4),
    ("Check valve, DN80, ductile iron", "8481.30", 18, 166.00, 9.2),
    ("Gate valve, DN100, ductile iron", "8481.80", 12, 241.00, 16.8),
    ("Variable frequency drive, 7.5 kW, IP55", "8504.40", 12, 1120.00, 9.6),
    ("Variable frequency drive, 15 kW, IP55", "8504.40", 6, 1890.00, 14.3),
    ("Control panel, duty and standby, 400 V", "8537.10", 4, 2360.00, 31.0),
    ("Float switch, cable 10 m", "8536.50", 20, 44.00, 0.7),
    ("Level sensor, hydrostatic, 4 to 20 mA", "9026.10", 8, 352.00, 1.1),
    ("Spare parts box, SP-40 wear parts", "8413.91", 10, 96.00, 2.6),
    ("Anti-vibration mounts, set of four", "4016.99", 22, 57.00, 1.8),
    ("Suction strainer, DN80, stainless steel", "8421.21", 12, 189.00, 4.4),
    ("Flange adaptor set, DN80 to DN100", "7307.91", 18, 73.50, 3.1),
    ("Installation and maintenance manuals, printed", "4901.99", 34, 0.00, 0.3),
]

TERMS = """\
Terms of sale: CIF Rotterdam (Incoterms 2020). Payment: 60 days from invoice date by bank transfer.
Origin of goods: as stated per line on the certificate of origin, DOC-5532. Currency: EUR.
The seller declares that the goods described above are new, that the prices shown are the prices actually paid
or payable, and that no royalties, assists or other payments not shown here are due in connection with the sale.
Goods remain the property of the seller until paid in full. Claims for shortage or damage must be made in writing
within 14 days of delivery, quoting this invoice number and the carton numbers concerned. Warranty: 24 months from
commissioning or 30 months from delivery, whichever comes first, excluding wear parts listed as such above.
Packing: export cartons and wooden crates on heat-treated pallets, marked with the consignee, the destination and
the carton number. Insurance: 110 percent of the CIF value, all risks, warehouse to warehouse."""


def invoice() -> str:
    lines = ["COMMERCIAL INVOICE INV-2026-0417 (document DOC-5531)", "Shipment SH-4471, consignee: Cobalt Freight client", ""]
    total = 0.0
    for number, (part, hs, quantity, price, _) in enumerate(PARTS, start=1):
        amount = quantity * price
        total += amount
        lines.append(f"Line {number:02}  {part}")
        lines.append(f"         HS {hs}  quantity {quantity}  unit price EUR {price:,.2f}  line total EUR {amount:,.2f}")
    lines += ["", f"Total value: EUR {total:,.2f}", "", TERMS]
    return "\n".join(lines)


def packing_list() -> str:
    lines = ["PACKING LIST PL-2026-0417 (document DOC-5530)", "Shipment SH-4471, consignee: Cobalt Freight client", ""]
    carton = 1
    for number, (part, _, quantity, _, kilograms) in enumerate(PARTS, start=1):
        cartons = max(1, round(quantity * kilograms / 120))
        net = quantity * kilograms
        lines.append(f"Line {number:02}  {part}")
        lines.append(
            f"         quantity {quantity}  cartons {carton:03} to {carton + cartons - 1:03}  "
            f"net {net:,.1f} kg  gross {net * 1.06:,.1f} kg"
        )
        carton += cartons
    lines += ["", f"Total cartons: {carton - 1}", "", TERMS]
    return "\n".join(lines)


DOCUMENT_TEXT = {"DOC-5531": invoice(), "DOC-5530": packing_list()}


@tool
def read_document(document_id: Annotated[str, "Document ID: DOC- followed by four digits"]) -> str:
    """Return the full text of a document in Cobalt's document store."""
    return DOCUMENT_TEXT.get(document_id, f"No text on file for {document_id}")


class Collapse(ToolResultCompactionStrategy):
    """Collapses every old tool-call group, then prints the length of each message it wrote in their place."""

    async def __call__(self, messages: list) -> bool:
        changed = await super().__call__(messages)
        written = [len(m.text) for m in included_messages(messages) if m.text.startswith("[Tool results: ")]
        if written:
            print(f"Collapsed before this run: {len(written)} tool-call groups, now messages of "
                  f"{', '.join(f'{n:,}' for n in written)} characters\n")
        return changed


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--compact", action="store_true", help="collapse old tool results at the start of each run")
compact = parser.parse_args().compact

if compact:
    history = InMemoryHistoryProvider()
    collapse = CompactionProvider(
        before_strategy=Collapse(keep_last_tool_call_groups=0),
        history_source_id=history.source_id,
    )
    agent = investigator(context_providers=[history, collapse])
else:
    agent = investigator()


async def main() -> None:
    for document_id, text in DOCUMENT_TEXT.items():
        print(f"{document_id}: {len(text):,} characters of text")
    print(f"Old tool results collapsed at the start of each run: {'yes' if compact else 'no'}\n")
    session = agent.create_session()
    for number, question in enumerate([CHECK_TASK, FOLLOW_UP], start=1):
        first = len(calls)
        if question == FOLLOW_UP:
            follow_up_first = first
        print(f"Question {number}: {question}\n")
        show(await agent.run(question, session=session, tools=[read_document]))
        print(f"\n{'Call':>6}{'Input tokens':>14}{'Cached':>8}")
        for index, call in enumerate(calls[first:], start=first + 1):
            print(f"{index:>6}{call['input']:>14,}{call['cached']:>8,}")
        print()
    total = sum(c["input"] for c in calls)
    cached = sum(c["cached"] for c in calls)
    print(f"{len(calls)} model calls, {total:,} input tokens, {cached:,} of them cached")
    units = sum(c["input"] - c["cached"] + c["cached"] * CACHED_PRICE for c in calls[follow_up_first:])
    print(f"Input cost of question 2, in uncached-token units: {units:,.0f}")


asyncio.run(main())
