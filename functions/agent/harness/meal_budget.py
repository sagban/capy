"""Size a suggestion like a normal meal for this slot. Remaining is a ceiling."""

from __future__ import annotations

from statistics import median
from typing import Any, Optional

from schemas import DiaryContext, InterpretMealRequest, MacroTotals

MAIN_MEALS = ("breakfast", "lunch", "dinner")


def _slot(value: str | None) -> str:
    return (value or "").strip().lower()


def _day_slot_totals(entries: list[Any], slot: str) -> Optional[tuple[float, float]]:
    calories = 0.0
    protein = 0.0
    found = False
    for entry in entries:
        if _slot(getattr(entry, "mealSlot", None)) != slot:
            continue
        grams = getattr(entry, "grams", None)
        per = getattr(entry, "per100g", None)
        if grams is None or per is None or float(grams) <= 0:
            continue
        factor = float(grams) / 100.0
        calories += float(per.calories) * factor
        protein += float(per.proteinG) * factor
        found = True
    if not found:
        return None
    return calories, protein


def _samples(req: InterpretMealRequest, slot: str) -> list[tuple[float, float]]:
    samples: list[tuple[float, float]] = []
    today = _day_slot_totals(list(req.diaryContext.today or []), slot)
    if today:
        samples.append(today)
    for day in req.diaryContext.previousDays or []:
        hit = _day_slot_totals(list(day.entries or []), slot)
        if hit:
            samples.append(hit)
    return samples


def logged_main_slots(diary: DiaryContext) -> set[str]:
    found: set[str] = set()
    for entry in diary.today or []:
        slot = _slot(entry.mealSlot)
        if slot in MAIN_MEALS:
            found.add(slot)
    return found


def slot_budget(
    req: InterpretMealRequest,
    meal_slot: str | None,
    stated: dict[str, Any] | None = None,
) -> dict[str, float | None]:
    """Calorie ceiling and optional protein floor for one meal slot."""
    remaining: MacroTotals = req.diaryContext.remaining
    rem_cal = max(float(remaining.calories), 0.0)
    if rem_cal <= 0:
        return {"calories": 0.0, "proteinG": 0.0}

    stated = stated or {}
    stated_cal = stated.get("calories")
    if stated_cal is not None:
        try:
            calories = min(float(stated_cal), rem_cal)
        except (TypeError, ValueError):
            calories = rem_cal
        protein = stated.get("proteinG")
        protein_out: float | None
        try:
            protein_out = float(protein) if protein is not None else None
        except (TypeError, ValueError):
            protein_out = None
        return {"calories": calories, "proteinG": protein_out}

    slot = _slot(meal_slot)
    samples = _samples(req, slot) if slot else []
    if slot and len(samples) >= 3:
        calories = min(float(median([s[0] for s in samples])), rem_cal)
        protein = float(median([s[1] for s in samples]))
        return {"calories": calories, "proteinG": protein}

    logged = logged_main_slots(req.diaryContext)
    if slot in MAIN_MEALS:
        # Meals earlier than the one they asked for are missed, not still ahead.
        # Dinner with only snacks logged is the rest of the day, not a third of it.
        start = MAIN_MEALS.index(slot)
        pending = [name for name in MAIN_MEALS[start:] if name == slot or name not in logged]
    else:
        pending = [name for name in MAIN_MEALS if name not in logged]
        if slot and slot not in pending:
            pending.append(slot)
    count = max(len(pending), 1)
    return {
        "calories": rem_cal / count,
        "proteinG": max(float(remaining.proteinG), 0.0) / count,
    }


def usual_foods(req: InterpretMealRequest, meal_slot: str | None, limit: int = 10) -> list[dict[str, Any]]:
    """Most frequent foods for a slot over the supplied diary, with median grams."""
    slot = _slot(meal_slot)
    if not slot:
        return []
    grouped: dict[str, list[float]] = {}
    names: dict[str, str] = {}

    def take(entries: list[Any]) -> None:
        for entry in entries:
            if _slot(getattr(entry, "mealSlot", None)) != slot:
                continue
            key = (getattr(entry, "foodId", None) or getattr(entry, "name", None) or "").strip()
            if not key:
                continue
            grams = getattr(entry, "grams", None)
            if grams is None:
                continue
            grouped.setdefault(key, []).append(float(grams))
            names[key] = getattr(entry, "name", None) or key

    take(list(req.diaryContext.today or []))
    for day in req.diaryContext.previousDays or []:
        take(list(day.entries or []))

    ranked = sorted(grouped.items(), key=lambda item: (-len(item[1]), names.get(item[0], "").lower()))
    out: list[dict[str, Any]] = []
    for key, grams in ranked[:limit]:
        out.append(
            {
                "foodId": key,
                "name": names.get(key, key),
                "times": len(grams),
                "typicalGrams": float(median(grams)),
            }
        )
    return out


def fit_label(
    calories: float,
    protein_g: float,
    budget: dict[str, float | None],
) -> str:
    """`within` when calories are at or under the slot ceiling. A smaller meal still fits.

    `protein_g` is reported on the option. It does not flip a meal under the ceiling to over.
    """
    del protein_g
    cap = float(budget.get("calories") or 0)
    if float(calories) > cap:
        return "over"
    return "within"
