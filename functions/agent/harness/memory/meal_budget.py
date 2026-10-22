"""Size a suggestion like a normal meal for this slot. Remaining macros are the ceiling."""

from __future__ import annotations

from statistics import median
from typing import Any, Literal, Optional

AppetiteLevel = Literal["light", "normal", "hearty"]

APPETITE_LEVELS: tuple[AppetiteLevel, ...] = ("light", "normal", "hearty")
APPETITE_TO_MULTIPLIER: dict[AppetiteLevel, float] = {
    "light": 0.85,
    "normal": 1.0,
    "hearty": 1.45,
}

from agent.harness.memory.meal_slots import (
    is_ancillary_slot,
    planned_slot_names,
    resolve_slot_name,
    slot_index_in_plan,
)
from schemas import DiaryContext, InterpretMealRequest, MacroTotals

# Snacks / out-of-plan: small flexible bite; finisher meal still owns the rest of the day.
_SNACK_CAL_MAX = 250.0
_SNACK_CAL_MIN = 100.0
_SNACK_CAL_FRACTION = 0.12
_SNACK_MACRO_FRACTION = 0.15
_SNACK_CAL_MAX_FLEX = 400.0


def _slot(value: str | None) -> str:
    return (value or "").strip().lower()


def _norm_name(value: str | None) -> str:
    return (value or "").strip()


def normalize_appetite(value: Any) -> AppetiteLevel:
    """Map caller appetite to a known level; unknown values default to normal."""
    if value is None:
        return "normal"
    key = str(value).strip().lower()
    if key in APPETITE_TO_MULTIPLIER:
        return key  # type: ignore[return-value]
    return "normal"


def appetite_scale(level: AppetiteLevel) -> float:
    return APPETITE_TO_MULTIPLIER[level]


def _remaining_macros(remaining: MacroTotals) -> MacroTotals:
    return MacroTotals(
        calories=max(float(remaining.calories), 0.0),
        proteinG=max(float(remaining.proteinG), 0.0),
        carbsG=max(float(remaining.carbsG), 0.0),
        fatG=max(float(remaining.fatG), 0.0),
    )


def _empty_budget() -> dict[str, float]:
    return {"calories": 0.0, "proteinG": 0.0, "carbsG": 0.0, "fatG": 0.0}


def _macro_dict(totals: MacroTotals) -> dict[str, float]:
    return {
        "calories": float(totals.calories),
        "proteinG": float(totals.proteinG),
        "carbsG": float(totals.carbsG),
        "fatG": float(totals.fatG),
    }


def _cap_macros_to(target: dict[str, float], ceiling: MacroTotals) -> dict[str, float]:
    return {
        "calories": min(target["calories"], ceiling.calories),
        "proteinG": min(target["proteinG"], ceiling.proteinG),
        "carbsG": min(target["carbsG"], ceiling.carbsG),
        "fatG": min(target["fatG"], ceiling.fatG),
    }


def _day_slot_totals(entries: list[Any], slot_key: str) -> Optional[MacroTotals]:
    calories = protein = carbs = fat = 0.0
    found = False
    for entry in entries:
        if _slot(getattr(entry, "mealSlot", None)) != slot_key:
            continue
        grams = getattr(entry, "grams", None)
        per = getattr(entry, "per100g", None)
        if grams is None or per is None or float(grams) <= 0:
            continue
        factor = float(grams) / 100.0
        calories += float(per.calories) * factor
        protein += float(per.proteinG) * factor
        carbs += float(per.carbsG) * factor
        fat += float(per.fatG) * factor
        found = True
    if not found:
        return None
    return MacroTotals(calories=calories, proteinG=protein, carbsG=carbs, fatG=fat)


def _samples(req: InterpretMealRequest, slot_name: str) -> list[MacroTotals]:
    slot_key = _slot(slot_name)
    samples: list[MacroTotals] = []
    today = _day_slot_totals(list(req.diaryContext.today or []), slot_key)
    if today:
        samples.append(today)
    for day in req.diaryContext.previousDays or []:
        hit = _day_slot_totals(list(day.entries or []), slot_key)
        if hit:
            samples.append(hit)
    return samples


def _median_macros(samples: list[MacroTotals]) -> MacroTotals:
    return MacroTotals(
        calories=float(median([s.calories for s in samples])),
        proteinG=float(median([s.proteinG for s in samples])),
        carbsG=float(median([s.carbsG for s in samples])),
        fatG=float(median([s.fatG for s in samples])),
    )


def default_share_for_plan_index(slot_index: int, plan_size: int) -> float:
    """Share of remaining when history is thin. The last planned meal uses what is left."""
    if plan_size <= 1:
        return 1.0
    if slot_index >= plan_size - 1:
        return 1.0
    if plan_size == 2:
        return 0.35
    # A breakfast / lunch / dinner day: 22%, then 35%, then whatever is left.
    if plan_size == 3:
        return 0.22 if slot_index == 0 else 0.35
    early_slots = plan_size - 1
    t = slot_index / max(early_slots - 1, 1)
    return 0.22 + t * 0.13


def _ancillary_budget(remaining: MacroTotals) -> dict[str, float]:
    cal = min(_SNACK_CAL_MAX, max(_SNACK_CAL_MIN, remaining.calories * _SNACK_CAL_FRACTION))
    cal = min(cal, remaining.calories)
    frac = _SNACK_MACRO_FRACTION
    return _cap_macros_to(
        {
            "calories": cal,
            "proteinG": remaining.proteinG * frac,
            "carbsG": remaining.carbsG * frac,
            "fatG": remaining.fatG * frac,
        },
        remaining,
    )


def _weighted_default(req: InterpretMealRequest, slot_name: str, remaining: MacroTotals) -> dict[str, float]:
    if is_ancillary_slot(slot_name, req):
        return _ancillary_budget(remaining)

    plan = planned_slot_names(req)
    resolved = resolve_slot_name(slot_name, req) or slot_name
    index = slot_index_in_plan(resolved, plan)

    if index is None:
        if plan:
            return _ancillary_budget(remaining)
        share = 0.35
    else:
        share = default_share_for_plan_index(index, len(plan))

    scaled = MacroTotals(
        calories=remaining.calories * share,
        proteinG=remaining.proteinG * share,
        carbsG=remaining.carbsG * share,
        fatG=remaining.fatG * share,
    )
    return _cap_macros_to(_macro_dict(scaled), remaining)


def _scale_snack_budget(
    base: dict[str, float],
    mult: float,
    remaining: MacroTotals,
) -> dict[str, float]:
    cap_cal = min(_SNACK_CAL_MAX_FLEX, remaining.calories * 0.2) if mult > 1.0 else remaining.calories
    out = {
        "calories": min(max(base["calories"] * mult, 0.0), cap_cal, remaining.calories),
        "proteinG": min(max(base["proteinG"] * mult, 0.0), remaining.proteinG),
        "carbsG": min(max(base["carbsG"] * mult, 0.0), remaining.carbsG),
        "fatG": min(max(base["fatG"] * mult, 0.0), remaining.fatG),
    }
    return out


def apply_appetite(
    guide: dict[str, float | None],
    *,
    appetite: AppetiteLevel,
    remaining: MacroTotals,
    req: InterpretMealRequest,
    slot_name: str,
) -> dict[str, float | None]:
    level = normalize_appetite(appetite)
    mult = appetite_scale(level)
    if mult == 1.0:
        return guide
    base = {k: float(guide.get(k) or 0) for k in ("calories", "proteinG", "carbsG", "fatG")}
    if is_ancillary_slot(slot_name, req):
        scaled = _scale_snack_budget(base, mult, remaining)
    else:
        scaled = _cap_macros_to(
            {key: value * mult for key, value in base.items()},
            remaining,
        )
    return {
        **scaled,
        "guideCalories": base["calories"],
        "guideProteinG": base["proteinG"],
        "guideCarbsG": base["carbsG"],
        "guideFatG": base["fatG"],
        "appetite": level,
    }


def _stated_budget(stated: dict[str, Any], remaining: MacroTotals) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key, rem_key in (
        ("calories", "calories"),
        ("proteinG", "proteinG"),
        ("carbsG", "carbsG"),
        ("fatG", "fatG"),
    ):
        raw = stated.get(key)
        if raw is None:
            out[key] = None
            continue
        try:
            out[key] = min(float(raw), getattr(remaining, rem_key))
        except (TypeError, ValueError):
            out[key] = None
    if out.get("calories") is None and any(out.get(k) is not None for k in ("proteinG", "carbsG", "fatG")):
        out["calories"] = remaining.calories
    if out.get("calories") is None:
        return {}
    return out


def slot_budget(
    req: InterpretMealRequest,
    meal_slot: str | None,
    stated: dict[str, Any] | None = None,
    *,
    appetite: AppetiteLevel | str = "normal",
) -> dict[str, float | None]:
    """Macro ceilings for one meal slot.

    Guide budgets (median / plan-weighted default) may be scaled by ``appetite``.
    Stated budgets from the model are capped per macro to remaining. Only remaining is a hard ceiling.
    """
    remaining = _remaining_macros(req.diaryContext.remaining)
    if remaining.calories <= 0:
        return _empty_budget()

    stated = stated or {}
    if stated.get("calories") is not None:
        explicit = _stated_budget(stated, remaining)
        if explicit.get("calories") is not None:
            return explicit

    plan = planned_slot_names(req)
    resolved = resolve_slot_name(meal_slot, req) or _norm_name(meal_slot) or (plan[0] if plan else "Meal")
    slot_key = _slot(resolved)
    samples = _samples(req, resolved) if slot_key else []
    if slot_key and len(samples) >= 3:
        median_totals = _median_macros(samples)
        guide = _cap_macros_to(_macro_dict(median_totals), remaining)
    else:
        guide = _weighted_default(req, resolved, remaining)

    return apply_appetite(
        guide,
        appetite=normalize_appetite(appetite),
        remaining=remaining,
        req=req,
        slot_name=resolved,
    )


def logged_main_slots(diary: DiaryContext) -> set[str]:
    """Deprecated alias: slots with food logged today (any name)."""
    from agent.harness.memory.meal_slots import logged_slot_keys_today

    return logged_slot_keys_today(diary)


def usual_foods(req: InterpretMealRequest, meal_slot: str | None, limit: int = 10) -> list[dict[str, Any]]:
    """Most frequent foods for a slot over the supplied diary, with median grams."""
    resolved = resolve_slot_name(meal_slot, req)
    slot_key = _slot(resolved)
    if not slot_key:
        return []
    grouped: dict[str, list[float]] = {}
    names: dict[str, str] = {}

    def take(entries: list[Any]) -> None:
        for entry in entries:
            if _slot(getattr(entry, "mealSlot", None)) != slot_key:
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
    *,
    carbs_g: float = 0.0,
    fat_g: float = 0.0,
) -> str:
    """``within`` when all capped macros are at or under the slot ceiling."""
    del protein_g
    caps = [
        ("calories", calories),
        ("carbsG", carbs_g),
        ("fatG", fat_g),
    ]
    for key, value in caps:
        cap = budget.get(key)
        if cap is None:
            continue
        if float(value) > float(cap):
            return "over"
    return "within"
