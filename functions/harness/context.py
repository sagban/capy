"""Context pack for one model turn. Last 8 turns stay verbatim."""

from __future__ import annotations

import json
from typing import Any

from harness.meal_budget import slot_budget, usual_foods
from schemas import InterpretMealRequest

_SLOTS = ("breakfast", "lunch", "dinner")


def compact_context_pack(req: InterpretMealRequest) -> str:
    wm = req.conversation.workingMemory
    turns = req.conversation.recentTurns or []
    recent = [t.model_dump() for t in turns[-8:]]
    older = turns[:-8]
    micro = ""
    if older:
        bits = []
        for turn in older[-6:]:
            role = (turn.role or "?")[:1]
            bits.append(f"{role}:{((turn.text or '')[:40])}")
        micro = " · ".join(bits)

    previous: list[dict[str, Any]] = []
    for day in req.diaryContext.previousDays or []:
        previous.append(
            {
                "dayKey": day.dayKey,
                "mealCount": day.mealCount,
                "entries": [e.model_dump() for e in (day.entries or [])],
            }
        )

    budgets = {slot: slot_budget(req, slot, None) for slot in _SLOTS}
    usual = {slot: usual_foods(req, slot) for slot in _SLOTS}
    memory = wm.model_dump(mode="json") if wm else None

    pack = {
        "utterance": req.utterance,
        "dayKey": req.dayKey,
        "timezone": req.timezone,
        "remaining": req.diaryContext.remaining.model_dump(),
        "slotBudgets": budgets,
        "usualFoods": usual,
        "today": [e.model_dump() for e in req.diaryContext.today],
        "previousDays": previous,
        "diets": req.preferenceContext.diets,
        "allergies": req.preferenceContext.allergies,
        "likes": req.preferenceContext.likes,
        "dislikes": req.preferenceContext.dislikes,
        "longTermMemory": [n.model_dump() for n in req.longTermMemory],
        "assistanceLevel": req.context.assistanceLevel,
        "summary": (req.conversation.summary or "")[:400],
        "olderTurnsCompact": micro,
        "recentTurns": recent,
        "workingMemory": memory,
    }
    return json.dumps(pack, ensure_ascii=False)
