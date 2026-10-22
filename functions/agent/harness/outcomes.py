"""Turn a tool trace into the client outcome, then check that shape."""

from __future__ import annotations

from typing import Any

from agent.harness.suggestions import suggestion_options
from schemas import (
    InterpretMealRequest,
    InterpretMealResponse,
    MealIntent,
    PendingAction,
    PendingActionPayload,
    PendingActionType,
    ResolvedItem,
    SuggestionOption,
    WorkingMemory,
)

BLOCKING = {
    PendingActionType.clarify_food,
    PendingActionType.clarify_portion,
    PendingActionType.confirm_log,
    PendingActionType.confirm_correction,
    PendingActionType.confirm_delete,
}


class OutcomeError(ValueError):
    pass


def _check_pending(response: InterpretMealResponse) -> None:
    pending = response.pendingAction
    if pending is None:
        return
    if pending.type not in BLOCKING:
        raise OutcomeError(f"pending {pending.type.value} is not a blocking outcome")
    payload = pending.payload
    if pending.type == PendingActionType.clarify_food:
        if payload.reason or payload.manualLog:
            return
        raise OutcomeError("clarify_food needs a reason")
    if pending.type == PendingActionType.clarify_portion:
        if payload.reason or payload.freeTextGrams:
            return
        raise OutcomeError("clarify_portion needs a reason or grams field")
    if pending.type == PendingActionType.confirm_log:
        if not payload.resolvedItems:
            raise OutcomeError("confirm_log needs items")
        for item in payload.resolvedItems:
            if item.grams <= 0 or item.per100g is None:
                raise OutcomeError("confirm_log item missing grams or per100g")
        return
    if pending.type == PendingActionType.confirm_correction:
        if not payload.entryId or payload.itemIndex is None:
            raise OutcomeError("confirm_correction needs entryId and itemIndex")
        if payload.correctionOp not in {"set_amount", "replace", "remove"}:
            raise OutcomeError("confirm_correction op")
        if payload.correctionOp != "remove" and not payload.resolvedItems:
            raise OutcomeError("confirm_correction needs the replacement item")
        return
    if pending.type == PendingActionType.confirm_delete:
        if not payload.entryId or not (payload.dayKey or "").strip():
            raise OutcomeError("confirm_delete needs entryId and dayKey")
        return


def _blank_memory(req: InterpretMealRequest) -> WorkingMemory:
    current = req.conversation.workingMemory
    if current is None:
        return WorkingMemory()
    return current.model_copy(deep=True)


def _pending(kind: PendingActionType, payload: PendingActionPayload) -> PendingAction:
    return PendingAction(type=kind, prompt="", payload=payload)


def _wrote(trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    for step in reversed(trace):
        result = step.get("result") if isinstance(step.get("result"), dict) else {}
        if step.get("name") in {"write_food_entry", "delete_food_entry"} and result.get("wrote"):
            return result
    return None


def _staged(trace: list[dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    for step in reversed(trace):
        if step.get("name") not in {"write_food_entry", "delete_food_entry"}:
            continue
        result = step.get("result") if isinstance(step.get("result"), dict) else {}
        if result.get("staged"):
            return str(step.get("name")), result
    return None


def outcome_from_trace(req: InterpretMealRequest, trace: list[dict[str, Any]]) -> dict[str, Any]:
    memory = _blank_memory(req)
    wrote = _wrote(trace)
    staged = _staged(trace)
    pending_action: PendingAction | None = None
    intent = MealIntent.unknown
    facts: dict[str, Any] = {}
    suggestions: list[SuggestionOption] = []

    if wrote is not None:
        intent = MealIntent.log_meal
        memory.pendingAction = None
        memory.pendingIntent = None
        memory.draftLog = []
        memory.resolveQueue = None
        facts = {"logged": True, "items": [{"displayName": "meal", "name": "meal"}]}
    elif staged is not None:
        name, result = staged
        items = [ResolvedItem.model_validate(row) for row in (result.get("items") or [])]
        if name == "delete_food_entry":
            intent = MealIntent.correct_meal
            pending_action = _pending(
                PendingActionType.confirm_delete,
                PendingActionPayload(
                    entryId=result.get("entryId"),
                    dayKey=result.get("dayKey"),
                    reason=result.get("label") or "meal",
                ),
            )
            facts = {"items": [{"displayName": result.get("label") or "meal"}]}
        elif result.get("pendingType") == PendingActionType.confirm_correction.value:
            intent = MealIntent.correct_meal
            pending_action = _pending(
                PendingActionType.confirm_correction,
                PendingActionPayload(
                    resolvedItems=items,
                    entryId=result.get("entryId"),
                    dayKey=result.get("dayKey"),
                    itemIndex=0,
                    correctionOp="replace",
                ),
            )
            facts = {"items": [item.model_dump(mode="json") for item in items]}
        else:
            intent = MealIntent.log_meal
            pending_action = _pending(
                PendingActionType.confirm_log,
                PendingActionPayload(resolvedItems=items),
            )
            facts = {"items": [item.model_dump(mode="json") for item in items]}
        memory.pendingAction = pending_action
        memory.pendingIntent = pending_action.type.value
        memory.draftLog = items
    else:
        suggestions = suggestion_options(trace, req.diaryContext.remaining)
        if suggestions:
            intent = MealIntent.suggest_meal
            memory.lastSuggestionOptions = suggestions
            facts = {"options": [option.model_dump(mode="json") for option in suggestions]}

    return {
        "intent": intent.value,
        "candidates": [],
        "clarifyingQuestion": None,
        "assistantMessage": "",
        "warnings": [],
        "memoryProposals": [],
        "pendingAction": pending_action.model_dump(mode="json") if pending_action else None,
        "suggestionOptions": [option.model_dump(mode="json") for option in suggestions],
        "workingMemory": memory.model_dump(mode="json"),
        "phraseFacts": facts,
    }


def normalize_outcome(payload: dict) -> dict:
    response = InterpretMealResponse.model_validate(payload)
    _check_pending(response)
    for option in response.suggestionOptions:
        if option.fit not in {"within", "over"}:
            raise OutcomeError(f"fit {option.fit}")
        if not option.items or option.totals is None:
            raise OutcomeError("suggestion option missing items or totals")
    return response.model_dump(mode="json")
