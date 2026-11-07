"""Chapter 5 demo: the document-store tool from the chapter's design, with the run's limits, against one failure at a time.

    uv run python ch05/document_tool.py --store down
    uv run python ch05/document_tool.py --store new-format
"""

import argparse
import asyncio
import logging
import time
from typing import Annotated

from agent_framework import Agent, tool
from pydantic import BaseModel, Field, ValidationError
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from agentlab.llm import make_client
from cobalt import get_customs_case, get_shipment_status, list_required_documents, store
from investigate import INSTRUCTIONS, TASK, show

ATTEMPTS = 3
STORE_TIMEOUT = 3  # seconds for each attempt
RUN_TIMEOUT = 130  # seconds: the run's two-minute budget, plus a margin

log = logging.getLogger("cobalt.tools")


class StoredDocument(BaseModel):
    document_id: str
    uploaded: str
    # required; null means not filed against any case
    filed_against_customs_case: str | None


@retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    stop=stop_after_attempt(ATTEMPTS),
    wait=wait_random_exponential(multiplier=0.5, max=4),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def search_store(shipment_id: str, document_type: str) -> dict | None:
    return store.search(shipment_id, document_type, timeout=STORE_TIMEOUT)


@tool
def find_document(
    shipment_id: Annotated[str, Field(pattern=r"^SH-\d{4}$", description="Shipment ID: SH- followed by four digits")],
    document_type: Annotated[str, "Document type in plain words. The store holds more types than any one customs case requires."],
) -> StoredDocument | dict:
    """Search Cobalt's document store for a shipment's document. Returns where it is filed, including the customs case it was uploaded against. A null filed_against_customs_case means the document is not filed against any case."""
    try:
        record = search_store(shipment_id, document_type)
    except (ConnectionError, TimeoutError) as error:
        log.error("find_document(%s, %s) failed after %d attempts: %s", shipment_id, document_type, ATTEMPTS, error)
        return {
            "error": f"The document store did not respond to {ATTEMPTS} attempts, so no search was made.",
            "document_exists": "unknown",
            "advice": "Do not search the document store again in this investigation. "
            "Do not conclude that the document is missing. Report that this check could not be done.",
        }
    if record is None:
        return {"found": False, "message": f"No {document_type} on file for {shipment_id}"}
    try:
        return StoredDocument.model_validate(record)
    except ValidationError as error:
        log.error("find_document(%s, %s): unexpected response from the document store: %s", shipment_id, document_type, error)
        return {
            "error": "The document store answered in a format this tool does not recognize, so the search result cannot be read.",
            "document_exists": "unknown",
            "advice": "Do not search the document store again in this investigation. "
            "Do not conclude that the document is missing. Report that this check could not be done.",
        }


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--store", choices=["normal", "down", "flaky", "slow", "new-format"], default="normal")
choice = parser.parse_args().store
if choice == "new-format":
    store.version = 2
else:
    store.behavior = choice

logging.basicConfig(format="%(levelname)s %(message)s")

client = make_client(timeout=30, max_retries=1)
client.function_invocation_configuration.update(max_iterations=9, max_function_calls=20, max_duration_seconds=60)
agent = Agent(client, INSTRUCTIONS, name="investigator",
              tools=[get_shipment_status, get_customs_case, list_required_documents, find_document])


async def investigate() -> None:
    async with asyncio.timeout(RUN_TIMEOUT):
        show(await agent.run(TASK))


print(f"Task: {TASK}  (the document store: {choice})\n")
start = time.monotonic()
try:
    asyncio.run(investigate())
except TimeoutError:
    print("No answer: the run did not finish in time. The case goes to a person.")
print(f"\nThe tool called the store {store.calls} times. The run took {time.monotonic() - start:.0f} seconds.")
