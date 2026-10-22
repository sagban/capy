"""In-app confirm gate. The first write stages until that pending action is already on the request."""

from __future__ import annotations

from typing import Any

from schemas import (
    InterpretMealRequest,
    MacroTotals,
    PendingAction,
    PendingActionPayload,
    PendingActionType,
    ResolvedItem,
)


def _opened_pending(req: InterpretMealRequest) -> PendingAction | None:
    memory = req.conversation.workingMemory
    if memory is None:
        return None
    return memory.pendingAction


def _diary_rows(req: InterpretMealRequest) -> list[Any]:
    rows: list[Any] = list(req.diaryContext.today or [])
    for day in req.diaryContext.previousDays or []:
        rows.extend(day.entries or [])
    return rows


def _entry_known(req: InterpretMealRequest, entry_id: str) -> bool:
    eid = (entry_id or "").strip()
    return any((getattr(row, "entryId", None) or "") == eid for row in _diary_rows(req))


def _entry_label(req: InterpretMealRequest, entry_id: str) -> str:
    names = [
        str(getattr(row, "name", "") or "").strip()
        for row in _diary_rows(req)
        if (getattr(row, "entryId", None) or "") == entry_id and getattr(row, "name", None)
    ]
    if not names:
        return "meal"
    if len(names) == 1:
        return names[0]
    label = ", ".join(names[:3])
    if len(names) > 3:
        label += ", …"
    return label


def _as_resolved(raw: dict[str, Any], index: int) -> ResolvedItem | None:
    per = raw.get("per100g")
    grams = raw.get("grams")
    name = str(raw.get("name") or raw.get("displayName") or "").strip()
    if not name or grams is None or per is None:
        return None
    try:
        totals = per if isinstance(per, MacroTotals) else MacroTotals.model_validate(per)
        amount = float(grams)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return ResolvedItem(
        foodId=str(raw.get("foodId") or f"log_{index}"),
        displayName=name,
        grams=round(amount, 2),
        per100g=totals,
        source=str(raw.get("source") or "catalog"),
        citationUrl=raw.get("citationUrl"),
        family=str(raw.get("ingredientFamily") or raw.get("family") or ""),
    )


def _same_macros(left: MacroTotals, right: MacroTotals) -> bool:
    return all(
        abs(float(getattr(left, key)) - float(getattr(right, key))) <= 0.05
        for key in ("calories", "proteinG", "carbsG", "fatG")
    )


def _same_items(staged: list[ResolvedItem], fresh: list[ResolvedItem]) -> bool:
    """The confirm is the same food, the same grams, and the same per-100g numbers."""
    if len(staged) != len(fresh):
        return False
    for left, right in zip(staged, fresh):
        if left.displayName.strip().lower() != right.displayName.strip().lower():
            return False
        if abs(float(left.grams) - float(right.grams)) > 0.2:
            return False
        if (left.foodId or "").strip() != (right.foodId or "").strip():
            return False
        if not _same_macros(left.per100g, right.per100g):
            return False
    return True


def gate_write(
    name: str,
    arguments: dict[str, Any],
    req: InterpretMealRequest,
    uid: str | None,
) -> dict[str, Any] | None:
    """Return a tool result when the in-app wrapper handles the write. None lets the tool run."""
    if name == "write_food_entry":
        return _gate_log(arguments, req, uid)
    if name == "delete_food_entry":
        return _gate_delete(arguments, req, uid)
    return None


def _entry_row(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": arguments.get("name"),
        "grams": arguments.get("grams"),
        "per100g": arguments.get("per100g"),
        "kind": arguments.get("kind"),
        "foodId": arguments.get("foodId"),
        "source": arguments.get("source"),
        "ingredientFamily": arguments.get("ingredientFamily"),
        "citationUrl": arguments.get("citationUrl"),
    }


def _gate_log(arguments: dict[str, Any], req: InterpretMealRequest, uid: str | None) -> dict[str, Any]:
    row = _entry_row(arguments)
    item = _as_resolved(row, 0)
    if item is None:
        return {"error": "bad_args", "message": "write_food_entry needs name, grams, and per100g"}
    resolved = [item]
    entry_id = (arguments.get("entry_id") or "").strip() or None
    if entry_id and not _entry_known(req, entry_id):
        return {"error": "bad_args", "message": "that entry is not in the diary"}
    opened = _opened_pending(req)
    if opened is not None and _confirms_log(opened, arguments, resolved, entry_id):
        from agent.tools.diary_io import write_food_entry

        if not uid:
            return {"error": "bad_args", "message": "write_food_entry needs a signed-in user"}
        per = arguments.get("per100g")
        written = write_food_entry(
            uid,
            str(arguments.get("day_key") or ""),
            str(arguments.get("meal_slot") or ""),
            str(arguments.get("kind") or "food"),
            str(arguments.get("name") or ""),
            float(arguments.get("grams") or 0),
            per if isinstance(per, dict) else {},
            foodId=arguments.get("foodId"),
            source=arguments.get("source"),
            ingredientFamily=arguments.get("ingredientFamily"),
            citationUrl=arguments.get("citationUrl"),
            entry_id=entry_id,
            client_mutation_id=arguments.get("client_mutation_id"),
        )
        if written.get("error"):
            return written
        return {**written, "wrote": True}
    payload = PendingActionPayload(resolvedItems=resolved, entryId=entry_id)
    if entry_id:
        payload.itemIndex = 0
        payload.correctionOp = "replace"
        payload.dayKey = str(arguments.get("day_key") or req.dayKey)
        kind = PendingActionType.confirm_correction
    else:
        kind = PendingActionType.confirm_log
    return {
        "staged": True,
        "pendingType": kind.value,
        "dayKey": str(arguments.get("day_key") or req.dayKey),
        "mealSlot": arguments.get("meal_slot"),
        "entryId": entry_id,
        "items": [item.model_dump(mode="json") for item in resolved],
    }


def _confirms_log(
    opened: PendingAction,
    arguments: dict[str, Any],
    resolved: list[ResolvedItem],
    entry_id: str | None,
) -> bool:
    del arguments
    if opened.type == PendingActionType.confirm_log and not entry_id:
        return _same_items(opened.payload.resolvedItems, resolved)
    if opened.type == PendingActionType.confirm_correction and entry_id:
        if (opened.payload.entryId or "") != entry_id:
            return False
        return _same_items(opened.payload.resolvedItems, resolved)
    return False


def _gate_delete(arguments: dict[str, Any], req: InterpretMealRequest, uid: str | None) -> dict[str, Any]:
    entry_id = str(arguments.get("entry_id") or "").strip()
    day_key = str(arguments.get("day_key") or "").strip()
    if not _entry_known(req, entry_id):
        return {"error": "bad_args", "message": "that meal is not in the diary"}
    opened = _opened_pending(req)
    if (
        opened is not None
        and opened.type == PendingActionType.confirm_delete
        and (opened.payload.entryId or "") == entry_id
        and (opened.payload.dayKey or "") == day_key
    ):
        from agent.tools.diary_io import delete_meal

        if not uid:
            return {"error": "bad_args", "message": "delete_food_entry needs a signed-in user"}
        written = delete_meal(uid, day_key, entry_id, arguments.get("client_mutation_id"))
        if written.get("error"):
            return written
        return {**written, "wrote": True}
    return {
        "staged": True,
        "pendingType": PendingActionType.confirm_delete.value,
        "dayKey": day_key,
        "entryId": entry_id,
        "label": _entry_label(req, entry_id),
    }
