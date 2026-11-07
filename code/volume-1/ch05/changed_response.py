"""Chapter 5 demo: the customs system changes how it reports documents. What does the model receive?"""

import argparse
import asyncio
import logging
from typing import Annotated

from agent_framework import tool
from pydantic import BaseModel, ValidationError

from cobalt import (
    RequiredDocuments,
    customs,
    find_document,
    get_customs_case,
    get_shipment_status,
    list_required_documents,
)
from investigate import TASK, investigator, show

log = logging.getLogger("cobalt.tools")


class DefaultedDocument(BaseModel):
    document: str
    received: bool = False  # a default, so that an entry without the flag is still accepted


class DefaultedDocuments(BaseModel):
    case_id: str
    documents: list[DefaultedDocument]


@tool(name="list_required_documents")
def defaulted_list_required_documents(
    case_id: Annotated[str, "Customs case ID: RTM- followed by five digits"],
) -> DefaultedDocuments | dict:
    """List the documents a customs case requires and whether customs has received each one."""
    documents = customs.required_documents(case_id)
    if not documents:
        return {"error": f"No document list for case {case_id}"}
    return DefaultedDocuments.model_validate({"case_id": case_id, "documents": documents})


@tool(name="list_required_documents")
def checked_list_required_documents(
    case_id: Annotated[str, "Customs case ID: RTM- followed by five digits"],
) -> RequiredDocuments | dict:
    """List the documents a customs case requires and whether customs has received each one."""
    documents = customs.required_documents(case_id)
    if not documents:
        return {"error": f"No document list for case {case_id}"}
    try:
        return RequiredDocuments.model_validate({"case_id": case_id, "documents": documents})
    except ValidationError as error:
        log.error("list_required_documents(%s): unexpected response from the customs system: %s", case_id, error)
        return {
            "error": "The customs system answered in a format this tool does not recognize, so it cannot say which documents customs has received.",
            "advice": "Do not conclude anything about which documents customs has received. Report that this check could not be done.",
        }


VARIANTS = {
    "typed": list_required_documents,  # cobalt.py's tool: required fields, no handling of a failed check
    "defaulted": defaulted_list_required_documents,
    "checked": checked_list_required_documents,
}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("variant", choices=VARIANTS, help="which list_required_documents tool to use")
variant = parser.parse_args().variant

customs.version = 2
agent = investigator([get_shipment_status, get_customs_case, VARIANTS[variant], find_document])
print(f"Task: {TASK}  (customs system version 2; the {variant} tool)\n")
show(asyncio.run(agent.run(TASK)))
