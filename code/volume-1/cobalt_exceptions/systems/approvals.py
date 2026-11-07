"""The approval queue: every refiling request the gate has seen, and what became of it."""

from ..domain.approval import RefilingRequest
from . import storage


def _all() -> dict:
    return storage.load("approvals", {})


def put(request: RefilingRequest) -> None:
    queue = _all()
    queue[request.request_id] = request.model_dump()
    storage.save("approvals", queue)


def get(request_id: str) -> RefilingRequest:
    return RefilingRequest.model_validate(_all()[request_id])


def everything() -> list[RefilingRequest]:
    return [RefilingRequest.model_validate(r) for r in _all().values()]


def next_id() -> str:
    return f"REQ-{len(_all()) + 1:04d}"
