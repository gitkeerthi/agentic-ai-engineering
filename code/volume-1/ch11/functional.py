"""Chapter 11 demo: the procedure's reads written with the framework's functional workflow API, which is
experimental in this version. No model call.

The same three reads as pipeline.py, as plain async functions: Python's own control flow gives the order, and
@step makes each call a step the run reports. The program prints the run's events, then its output.
"""

import asyncio

from agent_framework import step, workflow

from cobalt import customs_case, document_search, required_documents, shipment_status


@step
async def load_shipment(shipment_id: str) -> dict:
    return shipment_status(shipment_id)


@step
async def load_case(case_id: str) -> dict:
    return {
        "case": customs_case(case_id),
        "required": required_documents(case_id) or [],
    }


@step
async def check_documents(
    shipment_id: str, case_id: str, required: list[dict]
) -> dict:
    filings = {
        item["document"]: document_search(shipment_id, item["document"])
        for item in required
    }
    elsewhere = {
        f["filed_against_customs_case"]
        for f in filings.values()
        if f.get("filed_against_customs_case") not in (None, case_id)
    }
    return {
        "filings": filings,
        "other_cases": {other: customs_case(other) for other in sorted(elsewhere)},
    }


@workflow
async def gather(shipment_id: str) -> dict:
    shipment = await load_shipment(shipment_id)
    if "error" in shipment:
        return shipment
    if shipment["customs_case"] is None:  # ①
        return {"shipment": shipment, "customs_case": None}
    case = await load_case(shipment["customs_case"])
    documents = await check_documents(
        shipment_id, shipment["customs_case"], case["required"]
    )
    return {"shipment": shipment, **case, **documents}


async def main() -> None:
    result = await gather.build().run("SH-4471")
    for event in result:
        print(f"{event.type:<20} {event.executor_id or ''}")
    print(f"\nOutput: {result.get_outputs()[0]}")


asyncio.run(main())
