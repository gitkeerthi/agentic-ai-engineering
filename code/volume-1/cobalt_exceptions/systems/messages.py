"""Stand-in for Cobalt's message archive: customs messages and carrier notices, searchable by shipment.

A message's text is written by someone outside Cobalt, so whatever reads it treats it as evidence,
never as instructions. The archive can be busy; its client retries a few times before giving up.
"""

import re

from tenacity import retry

from .records import RETRY, Unavailable, answers_busy, load_records


@retry(**RETRY)
def search(shipment_id: str, query: str, limit: int = 5) -> list[dict]:
    """Messages about one shipment that share a word with the query, best match first."""
    if answers_busy("messages"):
        raise Unavailable("message archive busy")
    words = {w for w in re.findall(r"[a-z0-9-]+", query.lower()) if len(w) > 2}
    scored = []
    for message in load_records()["messages"]:
        if message["shipment_id"] != shipment_id:
            continue
        text = set(
            re.findall(
                r"[a-z0-9-]+",
                " ".join(str(v) for v in message.values() if v).lower(),
            )
        )
        score = len(words & text)
        if score:
            scored.append((score, message))
    scored.sort(key=lambda pair: -pair[0])
    return [message for _, message in scored[:limit]]


def latest(shipment_id: str, limit: int = 5) -> list[dict]:
    """The most recent messages about one shipment."""
    return [
        m for m in load_records()["messages"] if m["shipment_id"] == shipment_id
    ][-limit:][::-1]


def message(message_id: str) -> dict | None:
    return next(
        (m for m in load_records()["messages"] if m["message_id"] == message_id),
        None,
    )
