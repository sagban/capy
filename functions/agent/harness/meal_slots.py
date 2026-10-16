"""Meal slot names and order from the user's plan and diary — not a fixed breakfast/lunch/dinner list."""

from __future__ import annotations

from collections import Counter
from typing import Any

from schemas import DiaryContext, InterpretMealRequest, MealPlanSlot


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_key(value: str | None) -> str:
    return _norm(value).lower()


def meal_plan_from_context(diary: DiaryContext) -> list[MealPlanSlot]:
    """Enabled slots in sortOrder from the client meal plan."""
    plan = list(diary.mealPlan or [])
    enabled = [slot for slot in plan if slot.enabled and _norm(slot.name)]
    return sorted(enabled, key=lambda s: (s.sortOrder, _norm(s.name).lower()))


def _entries_with_slot(diary: DiaryContext) -> list[tuple[str, str]]:
    """(canonical slot name, norm key) from today and history."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def take(entries: list[Any]) -> None:
        for entry in entries:
            raw = _norm(getattr(entry, "mealSlot", None))
            if not raw:
                continue
            key = _norm_key(raw)
            if key in seen:
                continue
            seen.add(key)
            found.append((raw, key))

    take(list(diary.today or []))
    for day in diary.previousDays or []:
        take(list(day.entries or []))

    return found


def infer_slots_from_diary(diary: DiaryContext) -> list[str]:
    """When no meal plan is sent, infer slot names from diary usage (stable order of first seen)."""
    return [name for name, _ in _entries_with_slot(diary)]


def planned_slot_names(req: InterpretMealRequest) -> list[str]:
    plan = meal_plan_from_context(req.diaryContext)
    if plan:
        return [slot.name for slot in plan]
    inferred = infer_slots_from_diary(req.diaryContext)
    if inferred:
        return inferred
    return []


def resolve_slot_name(meal_slot: str | None, req: InterpretMealRequest) -> str:
    """Map free text to a plan slot name when possible (case-insensitive)."""
    raw = _norm(meal_slot)
    if not raw:
        return ""
    key = _norm_key(raw)
    for name in planned_slot_names(req):
        if _norm_key(name) == key:
            return name
    return raw


def logged_slot_keys_today(diary: DiaryContext) -> set[str]:
    keys: set[str] = set()
    for entry in diary.today or []:
        slot = _norm(entry.mealSlot)
        if slot:
            keys.add(_norm_key(slot))
    return keys


def slot_index_in_plan(slot_name: str, plan_names: list[str]) -> int | None:
    key = _norm_key(slot_name)
    for index, name in enumerate(plan_names):
        if _norm_key(name) == key:
            return index
    return None


def is_ancillary_slot(slot_name: str, req: InterpretMealRequest) -> bool:
    """Slots outside the plan, or explicit snack naming, use the small-bite budget."""
    if not _norm(slot_name):
        return False
    plan = planned_slot_names(req)
    if not plan:
        key = _norm_key(slot_name)
        return key in {"snack", "snacks"} or "snack" in key
    resolved = resolve_slot_name(slot_name, req)
    return slot_index_in_plan(resolved, plan) is None or _is_snack_label(resolved)


def _is_snack_label(name: str) -> bool:
    key = _norm_key(name)
    return key in {"snack", "snacks"} or "snack" in key


def pending_slots_from(slot_name: str, req: InterpretMealRequest) -> list[str]:
    """Plan slots from this meal through the end of the day that are still open (incl. target)."""
    plan = planned_slot_names(req)
    resolved = resolve_slot_name(slot_name, req) or slot_name
    if not plan or slot_index_in_plan(resolved, plan) is None:
        return [resolved] if _norm(resolved) else []
    logged = logged_slot_keys_today(req.diaryContext)
    start = slot_index_in_plan(resolved, plan) or 0
    pending: list[str] = []
    for name in plan[start:]:
        if _norm_key(name) == _norm_key(resolved) or _norm_key(name) not in logged:
            pending.append(name)
    return pending or [resolved]
