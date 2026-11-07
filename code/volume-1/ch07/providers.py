"""Chapter 7's context providers."""

import copy
import json
import re

from agent_framework import ContextProvider, FileHistoryProvider, Message

from cobalt import CUSTOMS_CASES, SHIPMENTS


class ShipmentStatus(ContextProvider):
    """Before each run, adds the current record of each shipment looked up earlier
    in the session. After each run, remembers which shipments the run looked up."""

    FIELDS = ["status", "location", "contents", "due", "customs_case"]  # only these

    def __init__(self) -> None:
        super().__init__("shipment_status")

    def current_records(self, state: dict) -> str | None:
        shipment_ids = state.get("shipment_ids", [])
        if not shipment_ids:
            return None
        lines = []
        for shipment_id in shipment_ids:
            record = SHIPMENTS.get(shipment_id)
            if record is None:
                lines.append(f"{shipment_id}: could not be read; "
                             "say so if asked")
                continue
            fields = {name: record[name] for name in self.FIELDS}
            if case := CUSTOMS_CASES.get(record["customs_case"] or ""):
                fields |= {"customs_case_status": case["status"],
                           "hold_reason": case["hold_reason"]}
            lines.append(f"{shipment_id}: {json.dumps(fields)}")
        heading = ("Current shipment records, read just before this run. "
                   "Records change over time: where these differ from earlier "
                   "messages, the shipment has changed since then.")
        return heading + "\n" + "\n".join(lines)

    async def before_run(self, *, agent, session, context, state) -> None:
        if note := self.current_records(state):
            context.extend_messages(self, [Message("user", [note])])

    async def after_run(self, *, agent, session, context, state) -> None:
        shipment_ids = state.setdefault("shipment_ids", [])
        for message in context.response.messages:
            for content in message.contents:
                if (content.type == "function_call"
                        and content.name == "get_shipment_status"):
                    shipment_id = content.parse_arguments().get("shipment_id")
                    if shipment_id in SHIPMENTS and shipment_id not in shipment_ids:
                        shipment_ids.append(shipment_id)


class RepairingFileHistory(FileHistoryProvider):
    """The framework's file-backed history, with one change: it leaves out any stored
    tool request that has no result, as a run that failed partway through can leave
    behind. A result counts if it is stored or arrives with this model call, because
    with saving after every model call, loading happens inside the run too."""

    async def before_run(self, *, agent, session, context, state) -> None:
        await super().before_run(
            agent=agent, session=session, context=context, state=state
        )
        history = context.context_messages.get(self.source_id, [])
        answered = {
            c.call_id
            for m in [*history, *context.input_messages]
            for c in m.contents
            if c.type == "function_result"
        }
        repaired = []
        for message in history:
            kept = [c for c in message.contents
                    if c.type != "function_call" or c.call_id in answered]
            if len(kept) < len(message.contents):
                message = copy.copy(message)
                message.contents = kept
            if kept:
                repaired.append(message)
        context.context_messages[self.source_id] = repaired


class Findings(ContextProvider):
    """After each investigation, keeps what the team will act on: the shipment, the
    cause, the action and the IDs. Before each run, puts those findings in front of
    the model. Chapter 6 did this by hand."""

    def __init__(self) -> None:
        super().__init__("findings")

    async def before_run(self, *, agent, session, context, state) -> None:
        if findings := state.get("findings"):
            entries = [
                f"{n}. {f['shipment']}. Cause: {f['cause']} Action: {f['action']} "
                f"IDs: {', '.join(f['ids'])}"
                for n, f in enumerate(findings, start=1)
            ]
            heading = ("Findings from earlier investigations in this conversation, "
                       "oldest first:")
            note = heading + "\n" + "\n".join(entries)
            context.extend_messages(self, [Message("user", [note])])

    async def after_run(self, *, agent, session, context, state) -> None:
        """Reads the answer's fixed format; Chapter 10's structured output
        makes this reliable."""
        task = " ".join(m.text for m in context.input_messages)
        answer = context.response.messages[-1].text
        shipment = re.search(r"SH-\d{4}", task)
        if shipment and "Cause" in answer:
            state.setdefault("findings", []).append({
                "shipment": shipment.group(),
                "cause": _line("Cause", answer),
                "action": _line("Recommended action", answer),
                "ids": sorted(set(re.findall(r"\b(?:SH|RTM|DOC)-\d+\b", answer))),
            })


def _line(label: str, answer: str) -> str:
    pattern = rf"^\W*(?:\w+ )?{label}[^:]*:\W*(.+)$"
    match = re.search(pattern, answer, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip(" *") if match else "(not stated)"
