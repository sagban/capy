"""Diary tool executors (new_entry / edit / delete / repeat)."""

from __future__ import annotations

from typing import Any, Optional

from agent.harness.portions import resolve_portion
from agent.harness.resolve import canonical_source, resolve_many
from agent.harness.tools.common import (
    apply_amount,
    base,
    blank_memory,
    chat,
    deps_deadline,
    diary_rows,
    item_results_from_resolved,
    pending,
    resolve_entry_day_key,
    results_to_outcome,
)
from schemas import (
    InterpretMealRequest,
    ItemDraft,
    MealIntent,
    MemoryProposal,
    PendingActionPayload,
    PendingActionType,
    ResolvedItem,
    WorkingMemory,
)

def _draft_items_from_memory(memory: WorkingMemory) -> list[ResolvedItem]:
    if memory.draftLog:
        return [item.model_copy(deep=True) for item in memory.draftLog]
    if memory.resolveQueue is not None:
        return [item.model_copy(deep=True) for item in memory.resolveQueue.resolved]
    return []


def _items_from_suggestion_option(
    req: InterpretMealRequest,
    memory: WorkingMemory,
    option_id: str,
) -> list[ResolvedItem] | dict[str, Any]:
    option = next((opt for opt in memory.lastSuggestionOptions if opt.id == option_id), None)
    if option is None:
        return chat(req, memory, {"reason": "that option is not in the last suggestions"})
    items: list[ResolvedItem] = []
    for raw in option.items:
        per = raw.per100g or raw.provisionalPer100g
        if per is None or raw.grams is None:
            return chat(req, memory, {"reason": "that option is missing a portion"})
        items.append(
            ResolvedItem(
                foodId=raw.foodId,
                displayName=raw.displayName,
                grams=float(raw.grams),
                per100g=per,
                source=canonical_source(raw.source),
                citationUrl=raw.citationUrl,
                portionLabel=raw.portionLabel,
                family=raw.family or "",
                measures=list(raw.measures or []),
            )
        )
    return items


def _apply_draft_ops(
    req: InterpretMealRequest,
    memory: WorkingMemory,
    items: list[ResolvedItem],
    ops: list[dict[str, Any]],
) -> tuple[list[ResolvedItem], list[ItemDraft], dict[str, Any] | None]:
    added: list[ItemDraft] = []
    for op in ops or []:
        kind = str(op.get("op") or "")
        index = op.get("index")
        if kind == "remove":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return items, added, chat(req, memory, {"reason": "that item is not in the open log"})
            del items[index]
            continue
        if kind == "set_amount":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return items, added, chat(req, memory, {"reason": "that item is not in the open log"})
            updated = apply_amount(items[index], float(op.get("quantity") or 0), op.get("unit"))
            if updated is None:
                return (
                    items,
                    added,
                    chat(req, memory, {"reason": "need a unit for that amount", "food": items[index].displayName}),
                )
            items[index] = updated
            continue
        if kind == "add":
            added.append(ItemDraft.model_validate(op.get("item") or {}))
            continue
        if kind == "replace":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return items, added, chat(req, memory, {"reason": "that item is not in the open log"})
            del items[index]
            added.append(ItemDraft.model_validate(op.get("item") or {}))
            continue
        return items, added, {"error": "bad_args", "message": f"unknown edit op {kind}"}
    return items, added, None


def new_entry(
    req: InterpretMealRequest,
    *,
    items: list[dict[str, Any]] | None = None,
    ops: list[dict[str, Any]] | None = None,
    option_id: str | None = None,
    memory: Optional[WorkingMemory] = None,
    proposals: Optional[list[MemoryProposal]] = None,
    correction: Optional[tuple[str, int, str]] = None,
) -> dict[str, Any]:
    """Stage a new meal entry (resolve foods, ops, or suggestion) for HITL confirm_log."""
    memory = memory or blank_memory(req)
    proposals = proposals or []
    if not option_id and not ops and not items:
        return {"error": "bad_args", "message": "new_entry needs optionId, ops, or items"}

    draft_items = _draft_items_from_memory(memory) if not option_id else []
    if option_id:
        loaded = _items_from_suggestion_option(req, memory, option_id)
        if isinstance(loaded, dict):
            return loaded
        draft_items = loaded

    added: list[ItemDraft] = []
    if ops:
        draft_items, added, err = _apply_draft_ops(req, memory, draft_items, ops)
        if err is not None:
            return err

    if items:
        added.extend(ItemDraft.model_validate(raw) for raw in items)

    resolved_prefix = item_results_from_resolved(draft_items) if draft_items else []
    if not added and not resolved_prefix:
        return chat(req, memory, {"reason": "the open log is empty"})

    if not added:
        memory.draftLog = draft_items
        return results_to_outcome(
            req,
            resolved_prefix,
            memory=memory,
            proposals=proposals,
            correction=correction,
        )

    deps, deadline = deps_deadline(req)
    tail = resolve_many(
        added,
        search=deps["search"],
        fetch_measures=deps["fetch_measures"],
        clock=deps["clock"],
        deadline=deadline,
    )
    return results_to_outcome(
        req,
        resolved_prefix + tail,
        memory=memory,
        proposals=proposals,
        correction=correction,
    )


def repeat_prior_meal(req: InterpretMealRequest, entry_ids: list[str]) -> dict[str, Any]:
    memory = blank_memory(req)
    wanted = {str(entry_id) for entry_id in entry_ids if entry_id}
    matched = [row for row in diary_rows(req) if row.entryId and row.entryId in wanted]
    items: list[ResolvedItem] = []
    for row in matched:
        if row.per100g is None or row.grams is None or float(row.grams) <= 0:
            continue
        items.append(
            ResolvedItem(
                foodId=row.foodId or f"diary_{row.entryId}_{row.itemIndex or 0}",
                displayName=row.name,
                grams=float(row.grams),
                per100g=row.per100g,
                source="diary",
                family=row.ingredientFamily or "",
                portionLabel=f"{float(row.grams):g} g",
                entryId=row.entryId,
                itemIndex=row.itemIndex,
            )
        )
    if not items:
        return chat(memory=memory, req=req, facts={"reason": "no matching meals in the diary"})
    return results_to_outcome(req, item_results_from_resolved(items), memory=memory, proposals=[])


def edit_entry(
    req: InterpretMealRequest,
    *,
    entry_id: str,
    item_index: int,
    op: str,
    quantity: float | None = None,
    unit: str | None = None,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    memory = blank_memory(req)
    target = next(
        (
            row
            for row in diary_rows(req)
            if row.entryId == entry_id and row.itemIndex == item_index
        ),
        None,
    )
    if target is None:
        return chat(req, memory, {"reason": "that diary item is not in context"})
    if op == "remove":
        pending_action = pending(
            PendingActionType.confirm_correction,
            PendingActionPayload(
                entryId=entry_id,
                itemIndex=item_index,
                correctionOp="remove",
                reason=target.name,
            ),
        )
        memory.draftLog = []
        memory.resolveQueue = None
        return base(
            intent=MealIntent.correct_meal,
            message_facts={"op": "remove", "food": target.name},
            memory=memory,
            pending_action=pending_action,
        )
    if op == "set_amount":
        if target.per100g is None or quantity is None:
            return {"error": "bad_args", "message": "set_amount needs quantity and stored per100g"}
        decision = resolve_portion(float(quantity), unit, [])
        if decision.grams is None:
            return {"error": "bad_args", "message": "set_amount needs a known unit"}
        resolved = ResolvedItem(
            foodId=target.foodId or f"diary_{entry_id}_{item_index}",
            displayName=target.name,
            grams=round(decision.grams, 2),
            per100g=target.per100g,
            source="diary",
            family=target.ingredientFamily or "",
            portionLabel=decision.label,
            entryId=entry_id,
            itemIndex=item_index,
        )
        return results_to_outcome(
            req,
            item_results_from_resolved([resolved]),
            memory=memory,
            proposals=[],
            correction=(entry_id, item_index, "set_amount"),
        )
    if op == "replace":
        if not item:
            return {"error": "bad_args", "message": "replace needs an item"}
        return new_entry(
            req,
            items=[item],
            memory=memory,
            correction=(entry_id, item_index, "replace"),
        )
    return {"error": "bad_args", "message": f"unknown correction op {op}"}


def delete_entry(
    req: InterpretMealRequest,
    *,
    entry_id: str,
    day_key: str | None = None,
) -> dict[str, Any]:
    """Stage removal of a whole diary entry for HITL confirm before delete_meal."""
    memory = blank_memory(req)
    eid = (entry_id or "").strip()
    if not eid:
        return {"error": "bad_args", "message": "delete_entry needs entryId"}
    resolved_day = resolve_entry_day_key(req, eid, day_key)
    if not resolved_day:
        return chat(req, memory, {"reason": "that meal is not in the diary pack"})
    rows = [row for row in diary_rows(req) if row.entryId == eid]
    if not rows:
        return chat(req, memory, {"reason": "that meal is not in the diary pack"})
    names = [str(row.name or "").strip() for row in rows if row.name]
    slot = next((row.mealSlot for row in rows if row.mealSlot), None)
    if len(names) == 1:
        label = names[0]
    elif names:
        label = ", ".join(names[:3])
        if len(names) > 3:
            label += ", …"
    else:
        label = "meal"
    if slot:
        label = f"{label} ({slot})"
    pending_action = pending(
        PendingActionType.confirm_delete,
        PendingActionPayload(
            entryId=eid,
            dayKey=resolved_day,
            reason=label,
        ),
    )
    memory.draftLog = []
    memory.resolveQueue = None
    return base(
        intent=MealIntent.correct_meal,
        message_facts={"op": "delete_entry", "entryId": eid, "dayKey": resolved_day, "label": label},
        memory=memory,
        pending_action=pending_action,
    )


