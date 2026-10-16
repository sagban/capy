"""Shared outcome builders for harness jobs."""

from __future__ import annotations

from typing import Any, Optional

from agent.harness.deps import resolve_deps
from agent.harness.portions import resolve_portion
from agent.harness.resolve import queue_from_results, queue_model
from schemas import (
    FoodCandidate,
    InterpretMealRequest,
    ItemDraft,
    MacroTotals,
    MealIntent,
    MemoryProposal,
    PendingAction,
    PendingActionPayload,
    PendingActionType,
    ResolvedItem,
    ResolveQueue,
    SuggestionOption,
    WorkingMemory,
    WorkingMemoryCandidate,
)

_TURN_SECONDS = 45.0


def scale(per: MacroTotals, grams: float) -> MacroTotals:
    factor = float(grams) / 100.0
    return MacroTotals(
        calories=round(per.calories * factor, 2),
        proteinG=round(per.proteinG * factor, 2),
        carbsG=round(per.carbsG * factor, 2),
        fatG=round(per.fatG * factor, 2),
    )


def blank_memory(req: InterpretMealRequest) -> WorkingMemory:
    current = req.conversation.workingMemory
    if current is None:
        return WorkingMemory()
    return current.model_copy(deep=True)


def diary_rows(req: InterpretMealRequest) -> list[Any]:
    rows: list[Any] = list(req.diaryContext.today or [])
    for day in req.diaryContext.previousDays or []:
        rows.extend(day.entries or [])
    return rows


def candidate(item: ResolvedItem) -> FoodCandidate:
    return FoodCandidate(
        foodId=item.foodId,
        displayName=item.displayName,
        grams=item.grams,
        source=item.source,
        provisionalPer100g=item.per100g,
        citationUrl=item.citationUrl,
    )


def wm_candidate(item: ResolvedItem) -> WorkingMemoryCandidate:
    return WorkingMemoryCandidate(
        foodId=item.foodId,
        displayName=item.displayName,
        grams=item.grams,
        source=item.source,
    )


def pending(kind: PendingActionType, payload: PendingActionPayload) -> PendingAction:
    return PendingAction(type=kind, prompt="", payload=payload)


def deps_deadline(req: InterpretMealRequest) -> tuple[dict[str, Any], float]:
    deps = resolve_deps(req)
    return deps, float(deps["clock"]()) + _TURN_SECONDS


def apply_amount(item: ResolvedItem, quantity: float, unit: str | None) -> Optional[ResolvedItem]:
    decision = resolve_portion(quantity, unit, item.measures)
    if decision.grams is None or decision.grams <= 0:
        return None
    updated = item.model_copy(deep=True)
    updated.grams = round(decision.grams, 2)
    updated.portionLabel = decision.label
    return updated


def memory_proposal(op: str, text: str | None, note_id: str | None) -> Optional[MemoryProposal]:
    if op == "add" and text:
        return MemoryProposal(action="add", text=text)
    if op == "remove" and note_id:
        return MemoryProposal(action="delete", id=note_id)
    return None


def base(
    *,
    intent: MealIntent,
    message_facts: dict[str, Any],
    memory: WorkingMemory,
    pending_action: Optional[PendingAction] = None,
    suggestions: Optional[list[SuggestionOption]] = None,
    budget: Optional[dict[str, Any]] = None,
    proposals: Optional[list[MemoryProposal]] = None,
    warnings: Optional[list[str]] = None,
    candidates: Optional[list[FoodCandidate]] = None,
) -> dict[str, Any]:
    memory.pendingAction = pending_action
    memory.pendingIntent = pending_action.type.value if pending_action else None
    memory.clarifyingQuestion = pending_action.prompt if pending_action else None
    if pending_action and pending_action.payload.resolvedItems:
        memory.candidates = [wm_candidate(item) for item in pending_action.payload.resolvedItems]
    elif memory.resolveQueue and memory.resolveQueue.clarifyOptions:
        memory.candidates = [
            WorkingMemoryCandidate(
                foodId=opt.foodId or opt.id,
                displayName=opt.label,
                grams=opt.grams,
                source=opt.source,
            )
            for opt in memory.resolveQueue.clarifyOptions
        ]
    return {
        "intent": intent.value,
        "candidates": [c.model_dump(mode="json") for c in (candidates or [])],
        "clarifyingQuestion": pending_action.prompt if pending_action else None,
        "assistantMessage": "",
        "warnings": list(warnings or []),
        "memoryProposals": [p.model_dump(mode="json") for p in (proposals or [])],
        "pendingAction": pending_action.model_dump(mode="json") if pending_action else None,
        "suggestionBudget": budget,
        "suggestionOptions": [o.model_dump(mode="json") for o in (suggestions or [])],
        "workingMemory": memory.model_dump(mode="json"),
        "phraseFacts": message_facts,
    }


def chat(
    req: InterpretMealRequest,
    memory: WorkingMemory,
    facts: dict[str, Any],
    proposals: Optional[list[MemoryProposal]] = None,
    budget: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    del req
    intent = MealIntent.update_memory if proposals else MealIntent.unknown
    return base(
        intent=intent,
        message_facts=facts,
        memory=memory,
        proposals=proposals,
        budget=budget,
    )


def results_to_outcome(
    req: InterpretMealRequest,
    results: list[Any],
    *,
    memory: WorkingMemory,
    proposals: list[MemoryProposal],
    suggestions: Optional[list[SuggestionOption]] = None,
    budget: Optional[dict[str, Any]] = None,
    correction: Optional[tuple[str, int, str]] = None,
) -> dict[str, Any]:
    del req
    resolved, paused, remaining = queue_from_results(results)
    if paused is None:
        items = resolved
        if correction and len(items) == 1:
            entry_id, index, op = correction
            items[0].entryId = entry_id
            items[0].itemIndex = index
            memory.draftLog = []
            memory.resolveQueue = None
            pending_action = pending(
                PendingActionType.confirm_correction,
                PendingActionPayload(
                    resolvedItems=items,
                    candidates=[wm_candidate(items[0])],
                    entryId=entry_id,
                    itemIndex=index,
                    correctionOp=op,
                ),
            )
            return base(
                intent=MealIntent.correct_meal,
                message_facts={"correction": items[0].model_dump(mode="json"), "op": op},
                memory=memory,
                pending_action=pending_action,
                proposals=proposals,
                candidates=[candidate(items[0])],
                suggestions=suggestions,
                budget=budget,
            )
        memory.draftLog = items
        memory.resolveQueue = None
        pending_action = pending(
            PendingActionType.confirm_log,
            PendingActionPayload(
                resolvedItems=items,
                candidates=[wm_candidate(item) for item in items],
            ),
        )
        return base(
            intent=MealIntent.log_meal,
            message_facts={"items": [item.model_dump(mode="json") for item in items]},
            memory=memory,
            pending_action=pending_action,
            proposals=proposals,
            candidates=[candidate(item) for item in items],
            suggestions=suggestions,
            budget=budget,
        )

    queue = queue_model(resolved, paused, remaining) or ResolveQueue()
    if correction:
        queue.correctionEntryId, queue.correctionItemIndex, queue.correctionOp = correction
    memory.resolveQueue = queue
    memory.draftLog = resolved
    if paused.status == "clarify_portion":
        pending_action = pending(
            PendingActionType.clarify_portion,
            PendingActionPayload(
                resolvedItems=resolved,
                freeTextGrams=bool(paused.free_text or not paused.options),
                reason=paused.reason,
            ),
        )
    else:
        pending_action = pending(
            PendingActionType.clarify_food,
            PendingActionPayload(
                resolvedItems=resolved,
                manualLog=bool(paused.manual_log),
                reason=paused.reason or "not_found",
                freeTextGrams=bool(paused.free_text),
            ),
        )
    return base(
        intent=MealIntent.clarify,
        message_facts={
            "reason": paused.reason,
            "kind": paused.status,
            "options": [opt.label for opt in paused.options],
            "food": paused.draft.foodQuery,
            "quantity": paused.draft.quantity,
            "unit": paused.draft.unit,
            "resolved": [item.displayName for item in resolved],
        },
        memory=memory,
        pending_action=pending_action,
        proposals=proposals,
        suggestions=suggestions,
        budget=budget,
    )


def item_results_from_resolved(items: list[ResolvedItem]) -> list[Any]:
    from agent.harness.resolve import ItemResult

    return [
        ItemResult(draft=ItemDraft(foodQuery=item.displayName), status="resolved", item=item) for item in items
    ]
