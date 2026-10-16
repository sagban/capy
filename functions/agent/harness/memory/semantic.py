"""User-stable facts derived from prefs and the diary. Numbers come from code."""

from __future__ import annotations

from typing import Any

from agent.harness.meal_budget import slot_budget, usual_foods
from schemas import InterpretMealRequest

_SLOTS = ("breakfast", "lunch", "dinner")


def _today_families(req: InterpretMealRequest) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for entry in req.diaryContext.today or []:
        family = (entry.ingredientFamily or "").strip().lower()
        if family and family not in seen:
            seen.add(family)
            found.append(family)
    return found


def semantic_block(req: InterpretMealRequest) -> dict[str, Any]:
    previous: list[dict[str, Any]] = []
    for day in req.diaryContext.previousDays or []:
        previous.append(
            {
                "dayKey": day.dayKey,
                "mealCount": day.mealCount,
                "entries": [e.model_dump() for e in (day.entries or [])],
            }
        )
    return {
        "dayKey": req.dayKey,
        "timezone": req.timezone,
        "remaining": req.diaryContext.remaining.model_dump(),
        "slotBudgets": {slot: slot_budget(req, slot, None) for slot in _SLOTS},
        "usualFoods": {slot: usual_foods(req, slot) for slot in _SLOTS},
        "today": [e.model_dump() for e in req.diaryContext.today],
        "todayFamilies": _today_families(req),
        "previousDays": previous,
        "constraints": {
            "diets": list(req.preferenceContext.diets or []),
            "allergies": list(req.preferenceContext.allergies or []),
            "likes": list(req.preferenceContext.likes or []),
            "dislikes": list(req.preferenceContext.dislikes or []),
        },
        "assistanceLevel": req.context.assistanceLevel,
    }
