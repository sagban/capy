"""Closed outcome check. One blocking pending action at most, and a valid shape."""

from __future__ import annotations

from schemas import InterpretMealResponse, PendingActionType

BLOCKING = {
    PendingActionType.clarify_food,
    PendingActionType.clarify_portion,
    PendingActionType.confirm_log,
    PendingActionType.confirm_correction,
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


def normalize_outcome(payload: dict) -> dict:
    response = InterpretMealResponse.model_validate(payload)
    _check_pending(response)
    for option in response.suggestionOptions:
        if option.fit not in {"within", "over"}:
            raise OutcomeError(f"fit {option.fit}")
        if not option.items or option.totals is None:
            raise OutcomeError("suggestion option missing items or totals")
    return response.model_dump(mode="json")
