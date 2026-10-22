"""Long-term notes. The harness proposes them; the client applies them. Not a model tool."""

from __future__ import annotations

import re
from typing import Any

from schemas import InterpretMealRequest, MemoryProposal

_PLEASE = re.compile(r"^please\s+", re.I)
_ADD = ("remember that ", "remember ", "note that ", "don't forget ")
_REMOVE = ("forget ", "remove the note ")


def memory_proposal(op: str, text: str | None, note_id: str | None) -> MemoryProposal | None:
    if op == "add" and text:
        return MemoryProposal(action="add", text=text)
    if op == "remove" and note_id:
        return MemoryProposal(action="delete", id=note_id)
    return None


def save_memory(
    op: str,
    text: str | None,
    note_id: str | None,
    proposals: list[MemoryProposal],
) -> dict[str, Any]:
    """Stage an add or remove of a long-term note. The client applies the proposal."""
    proposal = memory_proposal(op, text, note_id)
    if proposal is None:
        return {"error": "bad_args", "message": "save_memory needs add+text or remove+noteId"}
    proposals.append(proposal)
    return {"kind": "memory"}


def _strip_please(text: str) -> str:
    return _PLEASE.sub("", text.strip())


def proposals_for_utterance(req: InterpretMealRequest) -> list[MemoryProposal]:
    """Turn an explicit remember or forget into a proposal. Other utterances add nothing."""
    raw = _strip_please(req.utterance or "")
    lower = raw.lower()
    proposals: list[MemoryProposal] = []
    for prefix in _ADD:
        if lower.startswith(prefix):
            body = raw[len(prefix) :].strip(" .")
            save_memory("add", body, None, proposals)
            return proposals
    for prefix in _REMOVE:
        if not lower.startswith(prefix):
            continue
        body = raw[len(prefix) :].strip(" .")
        for note in req.longTermMemory or []:
            if (note.id or "") == body or (note.text or "").strip().lower() == body.lower():
                save_memory("remove", None, note.id, proposals)
                return proposals
    return proposals
