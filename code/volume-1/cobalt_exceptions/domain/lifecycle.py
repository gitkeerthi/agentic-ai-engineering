"""The case lifecycle: the states a case can be in, the moves allowed between them, and who may make each.

A case is opened when someone asks for an investigation and closed when customs releases the
shipment, the investigation shows nothing holds it, or a person closes it. A filing confirmed by
the document store is not a release: customs owns that, so a filed case waits until customs says so.
"""

from typing import Literal

State = Literal[
    "investigating",  # the workflow is reading the records and asking the agent
    "proposed",  # a refiling taken from the checked finding waits for a person's approval
    "with_person",  # a person owns the next step: a flag, a refusal, or an action only a person can take
    "approved",  # a person approved the refiling; the gate hasn't sent it yet
    "action_attempted",  # the gate sent the refiling to the document store
    "outcome_unknown",  # the store's reply never arrived: the filing may or may not exist
    "filed",  # the store confirmed the filing; customs hasn't released the shipment yet
    "closed",
]

# Each allowed move, with the authority that makes it.
TRANSITIONS: dict[tuple[str, str], str] = {
    ("investigating", "proposed"): "the workflow's checks and the gate",
    ("investigating", "with_person"): "the workflow's checks, or the gate (proposal refused)",
    ("investigating", "closed"): "the workflow's checks (nothing holds it)",
    ("proposed", "approved"): "an approver",
    ("proposed", "with_person"): "an approver (rejected) or the gate (expired)",
    ("approved", "action_attempted"): "the gate",
    ("action_attempted", "filed"): "the document store",
    (
        "action_attempted",
        "with_person",
    ): "the document store (refused, or the document changed)",
    ("action_attempted", "outcome_unknown"): "the gate (no reply from the store)",
    ("outcome_unknown", "filed"): "the document store, asked by the idempotency key",
    (
        "outcome_unknown",
        "action_attempted",
    ): "the gate (nothing filed under the key: send again)",
    ("filed", "closed"): "customs (the case is cleared)",
    ("filed", "with_person"): "the release check (customs hasn't cleared it in time)",
    ("with_person", "investigating"): "a person (investigate again)",
    ("with_person", "closed"): "a person",
}

OPEN_ACTION = {
    "proposed",
    "approved",
    "action_attempted",
    "outcome_unknown",
    "filed",
}


class IllegalTransition(ValueError):
    """A move the lifecycle doesn't allow."""


def move(current: str, to: str) -> str:
    """The authority for a move from one state to another; raises if the lifecycle forbids it."""
    if (current, to) not in TRANSITIONS:
        raise IllegalTransition(f"a case can't go from {current} to {to}")
    return TRANSITIONS[(current, to)]
