"""Thread-local conversation state: turns, summary, open working memory."""

from __future__ import annotations

from typing import Any

from schemas import InterpretMealRequest

RECENT_TURN_LIMIT = 8
OLDER_TURN_LIMIT = 6
OLDER_TEXT_CHARS = 40
SUMMARY_CHARS = 400


def thread_id(req: InterpretMealRequest) -> str:
    return (req.conversation.threadId or "default").strip() or "default"


def episodic_block(req: InterpretMealRequest) -> dict[str, Any]:
    wm = req.conversation.workingMemory
    turns = req.conversation.recentTurns or []
    recent = [t.model_dump() for t in turns[-RECENT_TURN_LIMIT:]]
    older = turns[:-RECENT_TURN_LIMIT]
    micro = ""
    if older:
        bits = []
        for turn in older[-OLDER_TURN_LIMIT:]:
            role = (turn.role or "?")[:1]
            bits.append(f"{role}:{((turn.text or '')[:OLDER_TEXT_CHARS])}")
        micro = " · ".join(bits)
    queue = wm.resolveQueue if wm else None
    open_work: dict[str, Any] = {}
    if queue and queue.pending:
        open_work = {
            "kind": "resolve_paused",
            "pendingFood": queue.pending.foodQuery,
            "quantity": queue.pending.quantity,
            "unit": queue.pending.unit,
            "options": [opt.label for opt in (queue.clarifyOptions or [])][:5],
            "remaining": [d.foodQuery for d in (queue.remaining or [])],
            "resolved": [item.displayName for item in (queue.resolved or [])],
        }
    elif wm and wm.draftLog:
        open_work = {
            "kind": "open_draft",
            "items": [f"{item.displayName} {item.grams:g} g" for item in wm.draftLog],
        }
    suggestions = []
    if wm:
        for opt in wm.lastSuggestionOptions or []:
            suggestions.append({"id": opt.id, "title": opt.title})
    return {
        "threadId": thread_id(req),
        "summary": (req.conversation.summary or "")[:SUMMARY_CHARS],
        "olderTurnsCompact": micro,
        "recentTurns": recent,
        "openWork": open_work or None,
        "lastSuggestionOptions": suggestions,
        "workingMemory": wm.model_dump(mode="json") if wm else None,
    }
