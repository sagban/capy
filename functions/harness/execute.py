"""Run terminal tools. The model picks the tool; this module does the work."""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from harness.deps import resolve_deps
from harness.meal_budget import fit_label, slot_budget
from harness.portions import resolve_portion
from harness.resolve import (
    canonical_source,
    queue_from_results,
    queue_model,
    resolve_many,
)
from schemas import (
    ClarifyOption,
    CommittedFood,
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
    SuggestionOptionItem,
    WorkingMemory,
    WorkingMemoryCandidate,
)

_TURN_SECONDS = 45.0


def lookup_menu(venue: str) -> dict[str, Any]:
    """Menu item names only. Digits in the grounded text are removed."""
    name = (venue or "").strip()
    if os.environ.get("CAPY_MOCK_AGENT") == "1":
        from harness.deps import _overrides

        scripted = _overrides.get("menu")
        if isinstance(scripted, dict):
            return scripted
        return {"venue": name, "items": ""}
    from web_search import web_search

    raw = web_search(f"{name} menu items")
    chunks: list[str] = []
    for row in raw.get("results") or []:
        if isinstance(row, dict) and row.get("summary"):
            chunks.append(str(row["summary"]))
    text = re.sub(r"\d+(?:\.\d+)?", " ", " ".join(chunks))
    text = re.sub(r"\s+", " ", text).strip()
    return {"venue": name, "items": text[:1500]}


def _scale(per: MacroTotals, grams: float) -> MacroTotals:
    factor = float(grams) / 100.0
    return MacroTotals(
        calories=round(per.calories * factor, 2),
        proteinG=round(per.proteinG * factor, 2),
        carbsG=round(per.carbsG * factor, 2),
        fatG=round(per.fatG * factor, 2),
    )


def _blank_memory(req: InterpretMealRequest) -> WorkingMemory:
    current = req.conversation.workingMemory
    if current is None:
        return WorkingMemory()
    return current.model_copy(deep=True)


def _diary_rows(req: InterpretMealRequest) -> list[Any]:
    rows: list[Any] = list(req.diaryContext.today or [])
    for day in req.diaryContext.previousDays or []:
        rows.extend(day.entries or [])
    return rows


def _candidate(item: ResolvedItem) -> FoodCandidate:
    return FoodCandidate(
        foodId=item.foodId,
        displayName=item.displayName,
        grams=item.grams,
        source=item.source,
        provisionalPer100g=item.per100g,
        citationUrl=item.citationUrl,
    )


def _wm_candidate(item: ResolvedItem) -> WorkingMemoryCandidate:
    return WorkingMemoryCandidate(
        foodId=item.foodId,
        displayName=item.displayName,
        grams=item.grams,
        source=item.source,
    )


def _base(
    *,
    intent: MealIntent,
    message_facts: dict[str, Any],
    memory: WorkingMemory,
    pending: Optional[PendingAction] = None,
    suggestions: Optional[list[SuggestionOption]] = None,
    budget: Optional[dict[str, Any]] = None,
    proposals: Optional[list[MemoryProposal]] = None,
    warnings: Optional[list[str]] = None,
    candidates: Optional[list[FoodCandidate]] = None,
) -> dict[str, Any]:
    memory.pendingAction = pending
    memory.pendingIntent = pending.type.value if pending else None
    memory.clarifyingQuestion = pending.prompt if pending else None
    if pending and pending.payload.resolvedItems:
        memory.candidates = [_wm_candidate(item) for item in pending.payload.resolvedItems]
    elif pending and pending.payload.clarifyOptions:
        memory.candidates = [
            WorkingMemoryCandidate(
                foodId=opt.foodId or opt.id,
                displayName=opt.label,
                grams=opt.grams,
                source=opt.source,
            )
            for opt in pending.payload.clarifyOptions
        ]
    return {
        "intent": intent.value,
        "candidates": [c.model_dump(mode="json") for c in (candidates or [])],
        "clarifyingQuestion": pending.prompt if pending else None,
        "assistantMessage": "",
        "warnings": list(warnings or []),
        "memoryProposals": [p.model_dump(mode="json") for p in (proposals or [])],
        "pendingAction": pending.model_dump(mode="json") if pending else None,
        "suggestionBudget": budget,
        "suggestionOptions": [o.model_dump(mode="json") for o in (suggestions or [])],
        "workingMemory": memory.model_dump(mode="json"),
        "phraseFacts": message_facts,
    }


def _pending(
    kind: PendingActionType,
    payload: PendingActionPayload,
) -> PendingAction:
    return PendingAction(type=kind, prompt="", payload=payload)


def _deps_deadline(req: InterpretMealRequest) -> tuple[dict[str, Any], float]:
    deps = resolve_deps(req)
    return deps, float(deps["clock"]()) + _TURN_SECONDS


def _results_to_outcome(
    req: InterpretMealRequest,
    results: list[Any],
    *,
    memory: WorkingMemory,
    proposals: list[MemoryProposal],
    suggestions: Optional[list[SuggestionOption]] = None,
    budget: Optional[dict[str, Any]] = None,
    correction: Optional[tuple[str, int, str]] = None,
) -> dict[str, Any]:
    resolved, paused, remaining = queue_from_results(results)
    if paused is None:
        items = resolved
        if correction and len(items) == 1:
            entry_id, index, op = correction
            items[0].entryId = entry_id
            items[0].itemIndex = index
            memory.draftLog = []
            memory.resolveQueue = None
            pending = _pending(
                PendingActionType.confirm_correction,
                PendingActionPayload(
                    resolvedItems=items,
                    candidates=[_wm_candidate(items[0])],
                    entryId=entry_id,
                    itemIndex=index,
                    correctionOp=op,
                ),
            )
            return _base(
                intent=MealIntent.correct_meal,
                message_facts={"correction": items[0].model_dump(mode="json"), "op": op},
                memory=memory,
                pending=pending,
                proposals=proposals,
                candidates=[_candidate(items[0])],
                suggestions=suggestions,
                budget=budget,
            )
        memory.draftLog = items
        memory.resolveQueue = None
        pending = _pending(
            PendingActionType.confirm_log,
            PendingActionPayload(
                resolvedItems=items,
                candidates=[_wm_candidate(item) for item in items],
            ),
        )
        return _base(
            intent=MealIntent.log_meal,
            message_facts={"items": [item.model_dump(mode="json") for item in items]},
            memory=memory,
            pending=pending,
            proposals=proposals,
            candidates=[_candidate(item) for item in items],
            suggestions=suggestions,
            budget=budget,
        )

    queue = queue_model(resolved, paused, remaining) or ResolveQueue()
    if correction:
        queue.correctionEntryId, queue.correctionItemIndex, queue.correctionOp = correction
    memory.resolveQueue = queue
    memory.draftLog = resolved
    if paused.status == "clarify_portion":
        pending = _pending(
            PendingActionType.clarify_portion,
            PendingActionPayload(
                clarifyOptions=paused.options,
                resolvedItems=resolved,
                freeTextGrams=bool(paused.free_text or not paused.options),
                reason=paused.reason,
            ),
        )
        intent = MealIntent.clarify
    else:
        pending = _pending(
            PendingActionType.clarify_food,
            PendingActionPayload(
                clarifyOptions=paused.options,
                resolvedItems=resolved,
                manualLog=bool(paused.manual_log),
                reason=paused.reason or "not_found",
                freeTextGrams=bool(paused.free_text),
            ),
        )
        intent = MealIntent.clarify
    return _base(
        intent=intent,
        message_facts={
            "reason": paused.reason,
            "options": [opt.label for opt in paused.options],
            "food": paused.draft.foodQuery,
            "resolved": [item.displayName for item in resolved],
        },
        memory=memory,
        pending=pending,
        proposals=proposals,
        suggestions=suggestions,
        budget=budget,
    )


def resolve_meal_call(
    req: InterpretMealRequest,
    items: list[dict[str, Any]],
    *,
    memory: Optional[WorkingMemory] = None,
    proposals: Optional[list[MemoryProposal]] = None,
    correction: Optional[tuple[str, int, str]] = None,
) -> dict[str, Any]:
    memory = memory or _blank_memory(req)
    proposals = proposals or []
    drafts = [ItemDraft.model_validate(item) for item in items]
    deps, deadline = _deps_deadline(req)
    results = resolve_many(
        drafts,
        search=deps["search"],
        fetch_measures=deps["fetch_measures"],
        web=deps["web"],
        clock=deps["clock"],
        deadline=deadline,
    )
    return _results_to_outcome(
        req,
        results,
        memory=memory,
        proposals=proposals,
        correction=correction,
    )


def _continue_queue(
    req: InterpretMealRequest,
    memory: WorkingMemory,
    resolved: list[ResolvedItem],
    remaining: list[ItemDraft],
    proposals: list[MemoryProposal],
) -> dict[str, Any]:
    queue = memory.resolveQueue
    correction = None
    if queue and queue.correctionEntryId and queue.correctionItemIndex is not None and queue.correctionOp:
        correction = (queue.correctionEntryId, queue.correctionItemIndex, queue.correctionOp)
    if not remaining:
        from harness.resolve import ItemResult

        results = [ItemResult(draft=ItemDraft(foodQuery=item.displayName), status="resolved", item=item) for item in resolved]
        return _results_to_outcome(
            req,
            results,
            memory=memory,
            proposals=proposals,
            correction=correction if len(resolved) == 1 else None,
        )
    deps, deadline = _deps_deadline(req)
    tail = resolve_many(
        remaining,
        search=deps["search"],
        fetch_measures=deps["fetch_measures"],
        web=deps["web"],
        clock=deps["clock"],
        deadline=deadline,
    )
    from harness.resolve import ItemResult

    head = [
        ItemResult(draft=ItemDraft(foodQuery=item.displayName), status="resolved", item=item) for item in resolved
    ]
    return _results_to_outcome(
        req,
        head + tail,
        memory=memory,
        proposals=proposals,
        correction=correction,
    )


def _committed_from_option(opt: ClarifyOption) -> Optional[CommittedFood]:
    if not opt.foodId or opt.per100g is None:
        return None
    return CommittedFood(
        foodId=opt.foodId,
        displayName=opt.label,
        per100g=opt.per100g,
        source=canonical_source(opt.source),
        citationUrl=opt.citationUrl,
        family=opt.family or "",
        measures=list(opt.measures or []),
    )


def _accept_kind(req: InterpretMealRequest, option_id: str) -> str:
    queue = req.conversation.workingMemory.resolveQueue if req.conversation.workingMemory else None
    if queue is None:
        return "pick_candidate"
    chosen = next((opt for opt in queue.clarifyOptions if opt.id == option_id), None)
    if chosen is not None and chosen.grams:
        return "pick_portion"
    return "pick_candidate"


def resume_action(req: InterpretMealRequest, action_type: str, action_id: str) -> dict[str, Any]:
    memory = _blank_memory(req)
    queue = memory.resolveQueue
    if action_type == "pick_option":
        return log_from_suggestion_call(req, action_id, ops=None, memory=memory)
    if queue is None or queue.pending is None:
        return _chat(req, memory, {"reason": "nothing open to continue"})

    chosen = next((opt for opt in queue.clarifyOptions if opt.id == action_id), None)
    if chosen is None:
        return _chat(req, memory, {"reason": "that choice is not one of the open options"})

    if action_type == "pick_portion" or (chosen.grams and queue.committed):
        committed = queue.committed
        grams = chosen.grams
        if committed is None or grams is None or grams <= 0:
            return _chat(req, memory, {"reason": "that portion is missing a weight"})
        item = ResolvedItem(
            foodId=committed.foodId,
            displayName=committed.displayName,
            grams=round(float(grams), 2),
            per100g=committed.per100g,
            source=committed.source,
            citationUrl=committed.citationUrl,
            portionLabel=chosen.label,
            family=committed.family,
            measures=list(committed.measures),
        )
        return _continue_queue(req, memory, list(queue.resolved) + [item], list(queue.remaining), [])

    committed = _committed_from_option(chosen)
    if committed is None:
        return _chat(req, memory, {"reason": "that food has no nutrition"})
    decision = resolve_portion(queue.pending.quantity, queue.pending.unit, committed.measures)
    if decision.grams is not None and decision.grams > 0:
        item = ResolvedItem(
            foodId=committed.foodId,
            displayName=committed.displayName,
            grams=round(decision.grams, 2),
            per100g=committed.per100g,
            source=committed.source,
            citationUrl=committed.citationUrl,
            portionLabel=decision.label,
            family=committed.family,
            measures=list(committed.measures),
        )
        return _continue_queue(req, memory, list(queue.resolved) + [item], list(queue.remaining), [])

    from harness.resolve import ItemResult

    paused = ItemResult(
        draft=queue.pending,
        status="clarify_portion",
        committed=committed,
        options=[],
        reason="need_amount",
        free_text=decision.free_text or not decision.chips,
    )
    from harness.resolve import _portion_options

    paused.options = _portion_options(committed, decision.chips)
    head_results = []
    from harness.resolve import ItemResult as IR

    for item in queue.resolved:
        head_results.append(IR(draft=ItemDraft(foodQuery=item.displayName), status="resolved", item=item))
    head_results.append(paused)
    for draft in queue.remaining:
        head_results.append(IR(draft=draft, status="clarify_food", reason="queued"))
    # queue_from_results stops at first non-resolved, so the paused portion is the stop
    # and remaining drafts stay drafts. Marking them clarify_food would pause on the
    # first of those if the portion resolved — it didn't. Good.
    correction = None
    if queue.correctionEntryId and queue.correctionItemIndex is not None and queue.correctionOp:
        correction = (queue.correctionEntryId, int(queue.correctionItemIndex), queue.correctionOp)
    return _results_to_outcome(req, head_results, memory=memory, proposals=[], correction=correction)


def _apply_amount(item: ResolvedItem, quantity: float, unit: str | None) -> Optional[ResolvedItem]:
    decision = resolve_portion(quantity, unit, item.measures)
    if decision.grams is None or decision.grams <= 0:
        return None
    updated = item.model_copy(deep=True)
    updated.grams = round(decision.grams, 2)
    updated.portionLabel = decision.label
    return updated


def edit_draft_call(req: InterpretMealRequest, ops: list[dict[str, Any]]) -> dict[str, Any]:
    memory = _blank_memory(req)
    items = [item.model_copy(deep=True) for item in (memory.draftLog or [])]
    if not items and memory.resolveQueue is not None:
        items = [item.model_copy(deep=True) for item in memory.resolveQueue.resolved]
    added: list[ItemDraft] = []
    for op in ops or []:
        kind = str(op.get("op") or "")
        index = op.get("index")
        if kind == "remove":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return _chat(req, memory, {"reason": "that item is not in the open log"})
            del items[index]
            continue
        if kind == "set_amount":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return _chat(req, memory, {"reason": "that item is not in the open log"})
            updated = _apply_amount(items[index], float(op.get("quantity") or 0), op.get("unit"))
            if updated is None:
                return _chat(req, memory, {"reason": "need a unit for that amount", "food": items[index].displayName})
            items[index] = updated
            continue
        if kind == "add":
            added.append(ItemDraft.model_validate(op.get("item") or {}))
            continue
        if kind == "replace":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return _chat(req, memory, {"reason": "that item is not in the open log"})
            del items[index]
            added.append(ItemDraft.model_validate(op.get("item") or {}))
            continue
        return {"error": "bad_args", "message": f"unknown edit op {kind}"}

    from harness.resolve import ItemResult

    resolved_results = [
        ItemResult(draft=ItemDraft(foodQuery=item.displayName), status="resolved", item=item) for item in items
    ]
    if not added and not items:
        return _chat(req, memory, {"reason": "the open log is empty"})
    if not added:
        memory.draftLog = items
        return _results_to_outcome(req, resolved_results, memory=memory, proposals=[])

    deps, deadline = _deps_deadline(req)
    tail = resolve_many(
        added,
        search=deps["search"],
        fetch_measures=deps["fetch_measures"],
        web=deps["web"],
        clock=deps["clock"],
        deadline=deadline,
    )
    return _results_to_outcome(req, resolved_results + tail, memory=memory, proposals=[])


def log_from_suggestion_call(
    req: InterpretMealRequest,
    option_id: str,
    ops: list[dict[str, Any]] | None,
    memory: Optional[WorkingMemory] = None,
) -> dict[str, Any]:
    memory = memory or _blank_memory(req)
    option = next((opt for opt in memory.lastSuggestionOptions if opt.id == option_id), None)
    if option is None:
        return _chat(req, memory, {"reason": "that option is not in the last suggestions"})
    items: list[ResolvedItem] = []
    for raw in option.items:
        per = raw.per100g or raw.provisionalPer100g
        if per is None or raw.grams is None:
            return _chat(req, memory, {"reason": "that option is missing a portion"})
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
    if ops:
        for op in ops:
            kind = str(op.get("op") or "")
            index = op.get("index")
            if kind == "set_amount" and isinstance(index, int) and 0 <= index < len(items):
                updated = _apply_amount(items[index], float(op.get("quantity") or 0), op.get("unit"))
                if updated is None:
                    return _chat(req, memory, {"reason": "need a unit for that amount", "food": items[index].displayName})
                items[index] = updated
            elif kind == "remove" and isinstance(index, int) and 0 <= index < len(items):
                del items[index]
    memory.draftLog = items
    from harness.resolve import ItemResult

    results = [
        ItemResult(draft=ItemDraft(foodQuery=item.displayName), status="resolved", item=item) for item in items
    ]
    return _results_to_outcome(req, results, memory=memory, proposals=[])


def _token_conflict(name: str, family: str, terms: list[str]) -> bool:
    blob = f"{name} {family}".lower()
    tokens = set(re.findall(r"[a-z0-9]+", blob))
    for term in terms:
        parts = re.findall(r"[a-z0-9]+", (term or "").lower())
        if parts and all(part in tokens or part in blob for part in parts):
            return True
    return False


def _today_families(req: InterpretMealRequest) -> set[str]:
    found: set[str] = set()
    for entry in req.diaryContext.today or []:
        family = (entry.ingredientFamily or "").strip().lower()
        if family:
            found.add(family)
    return found


def compose_suggestions_call(
    req: InterpretMealRequest,
    *,
    meal_slot: str | None,
    budget: dict[str, Any] | None,
    drafts: list[dict[str, Any]],
    memory: Optional[WorkingMemory] = None,
    proposals: Optional[list[MemoryProposal]] = None,
) -> dict[str, Any]:
    memory = memory or _blank_memory(req)
    proposals = proposals or []
    sized = slot_budget(req, meal_slot, budget)
    blocked = list(req.preferenceContext.allergies or []) + list(req.preferenceContext.dislikes or [])
    families = _today_families(req)
    deps, deadline = _deps_deadline(req)
    options: list[SuggestionOption] = []
    dropped: list[str] = []
    for index, draft in enumerate(drafts or []):
        title = str(draft.get("title") or f"Option {index + 1}")
        raw_items = list(draft.get("items") or [])
        if not raw_items:
            dropped.append(f"{title}: no items")
            continue
        item_drafts: list[ItemDraft] = []
        missing_amount = False
        for raw in raw_items:
            if raw.get("quantity") is None or not raw.get("unit"):
                missing_amount = True
                break
            item_drafts.append(
                ItemDraft(
                    foodQuery=str(raw.get("foodQuery") or ""),
                    quantity=float(raw["quantity"]),
                    unit=str(raw.get("unit")),
                    brandOrVenue=raw.get("brandOrVenue"),
                    aliases=list(raw.get("aliases") or []),
                )
            )
        if missing_amount or any(not item.foodQuery for item in item_drafts):
            dropped.append(f"{title}: missing amount")
            continue
        results = resolve_many(
            item_drafts,
            search=deps["search"],
            fetch_measures=deps["fetch_measures"],
            web=deps["web"],
            clock=deps["clock"],
            deadline=deadline,
        )
        if any(result.status != "resolved" or result.item is None for result in results):
            dropped.append(f"{title}: unresolved")
            continue
        resolved = [result.item for result in results if result.item is not None]
        if any(_token_conflict(item.displayName, item.family, blocked) for item in resolved):
            dropped.append(f"{title}: restriction")
            continue
        if any(item.family and item.family.lower() in families for item in resolved):
            dropped.append(f"{title}: already eaten")
            continue
        totals = MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
        option_items: list[SuggestionOptionItem] = []
        for item in resolved:
            scaled = _scale(item.per100g, item.grams)
            totals.calories += scaled.calories
            totals.proteinG += scaled.proteinG
            totals.carbsG += scaled.carbsG
            totals.fatG += scaled.fatG
            option_items.append(
                SuggestionOptionItem(
                    foodId=item.foodId,
                    displayName=item.displayName,
                    grams=item.grams,
                    source=item.source,
                    per100g=item.per100g,
                    provisionalPer100g=item.per100g,
                    citationUrl=item.citationUrl,
                    portionLabel=item.portionLabel,
                    family=item.family,
                    measures=list(item.measures),
                )
            )
        totals.calories = round(totals.calories, 2)
        totals.proteinG = round(totals.proteinG, 2)
        totals.carbsG = round(totals.carbsG, 2)
        totals.fatG = round(totals.fatG, 2)
        label = fit_label(totals.calories, totals.proteinG, sized)
        if float(req.diaryContext.remaining.calories) <= 0:
            label = "over"
        options.append(
            SuggestionOption(
                id=f"opt{index + 1}",
                title=title,
                reason="",
                items=option_items,
                totals=totals,
                fit=label,  # type: ignore[arg-type]
            )
        )
    memory.lastSuggestionOptions = options
    budget_out = {
        "calories": float(sized["calories"] or 0),
        **({"proteinG": float(sized["proteinG"])} if sized.get("proteinG") is not None else {}),
    }
    if not options:
        return _chat(
            req,
            memory,
            {"reason": "no suggestion survived", "dropped": dropped, "budget": budget_out},
            proposals=proposals,
            budget=budget_out,
        )
    return _base(
        intent=MealIntent.suggest_meal,
        message_facts={
            "budget": budget_out,
            "options": [
                {
                    "id": opt.id,
                    "title": opt.title,
                    "fit": opt.fit,
                    "totals": opt.totals.model_dump() if opt.totals else None,
                    "items": [
                        f"{int(round(item.grams))} g {item.displayName}" if item.grams else item.displayName
                        for item in opt.items
                    ],
                }
                for opt in options
            ],
        },
        memory=memory,
        suggestions=options,
        budget=budget_out,
        proposals=proposals,
    )


def repeat_prior_meal_call(req: InterpretMealRequest, entry_ids: list[str]) -> dict[str, Any]:
    memory = _blank_memory(req)
    wanted = {str(entry_id) for entry_id in entry_ids if entry_id}
    matched = [row for row in _diary_rows(req) if row.entryId and row.entryId in wanted]
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
        return _chat(memory=memory, req=req, facts={"reason": "no matching meals in the diary"})
    from harness.resolve import ItemResult

    results = [
        ItemResult(draft=ItemDraft(foodQuery=item.displayName), status="resolved", item=item) for item in items
    ]
    return _results_to_outcome(req, results, memory=memory, proposals=[])


def correct_entry_call(
    req: InterpretMealRequest,
    *,
    entry_id: str,
    item_index: int,
    op: str,
    quantity: float | None = None,
    unit: str | None = None,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    memory = _blank_memory(req)
    target = next(
        (
            row
            for row in _diary_rows(req)
            if row.entryId == entry_id and row.itemIndex == item_index
        ),
        None,
    )
    if target is None:
        return _chat(req, memory, {"reason": "that diary item is not in context"})
    if op == "remove":
        pending = _pending(
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
        return _base(
            intent=MealIntent.correct_meal,
            message_facts={"op": "remove", "food": target.name},
            memory=memory,
            pending=pending,
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
        from harness.resolve import ItemResult

        return _results_to_outcome(
            req,
            [ItemResult(draft=ItemDraft(foodQuery=target.name), status="resolved", item=resolved)],
            memory=memory,
            proposals=[],
            correction=(entry_id, item_index, "set_amount"),
        )
    if op == "replace":
        if not item:
            return {"error": "bad_args", "message": "replace needs an item"}
        return resolve_meal_call(
            req,
            [item],
            memory=memory,
            correction=(entry_id, item_index, "replace"),
        )
    return {"error": "bad_args", "message": f"unknown correction op {op}"}


def _memory_proposal(op: str, text: str | None, note_id: str | None) -> Optional[MemoryProposal]:
    if op == "add" and text:
        return MemoryProposal(action="add", text=text)
    if op == "remove" and note_id:
        return MemoryProposal(action="delete", id=note_id)
    return None


def _chat(
    req: InterpretMealRequest,
    memory: WorkingMemory,
    facts: dict[str, Any],
    proposals: Optional[list[MemoryProposal]] = None,
    budget: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    intent = MealIntent.update_memory if proposals else MealIntent.unknown
    return _base(
        intent=intent,
        message_facts=facts,
        memory=memory,
        proposals=proposals,
        budget=budget,
    )


def run_calls(req: InterpretMealRequest, calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute one turn's terminal calls. `save_memory` can ride along with any of them."""
    memory = _blank_memory(req)
    proposals: list[MemoryProposal] = []
    primary: Optional[dict[str, Any]] = None
    suggestions: Optional[dict[str, Any]] = None
    for call in calls:
        name = str(call.get("name") or "")
        args = call.get("arguments") or {}
        if name == "save_memory":
            proposal = _memory_proposal(str(args.get("op") or ""), args.get("text"), args.get("noteId"))
            if proposal is None:
                return {"error": "bad_args", "message": "save_memory needs add+text or remove+noteId"}
            proposals.append(proposal)
            continue
        if name == "accept_option":
            primary = resume_action(req, _accept_kind(req, str(args.get("optionId") or "")), str(args.get("optionId") or ""))
            continue
        if name in {"_action"}:
            action = args
            primary = resume_action(req, str(action.get("type") or ""), str(action.get("id") or ""))
            continue
        if name == "resolve_meal":
            primary = resolve_meal_call(
                req,
                list(args.get("items") or []),
                memory=memory,
                proposals=proposals,
            )
            continue
        if name == "edit_draft":
            primary = edit_draft_call(req, list(args.get("ops") or []))
            continue
        if name == "log_from_suggestion":
            primary = log_from_suggestion_call(
                req,
                str(args.get("optionId") or ""),
                list(args.get("ops") or []) or None,
                memory=memory,
            )
            continue
        if name == "compose_suggestions":
            suggestions = compose_suggestions_call(
                req,
                meal_slot=args.get("mealSlot"),
                budget=args.get("budget"),
                drafts=list(args.get("drafts") or []),
                memory=memory,
                proposals=proposals,
            )
            continue
        if name == "repeat_prior_meal":
            primary = repeat_prior_meal_call(req, list(args.get("entryIds") or []))
            continue
        if name == "correct_entry":
            primary = correct_entry_call(
                req,
                entry_id=str(args.get("entryId") or ""),
                item_index=int(args.get("itemIndex")),
                op=str(args.get("op") or ""),
                quantity=args.get("quantity"),
                unit=args.get("unit"),
                item=args.get("item"),
            )
            continue
        return {"error": "bad_args", "message": f"unknown tool {name}"}

    if primary and primary.get("error"):
        return primary
    if suggestions and suggestions.get("error"):
        return suggestions
    if primary and suggestions:
        merged = dict(primary)
        merged["suggestionOptions"] = suggestions.get("suggestionOptions") or []
        merged["suggestionBudget"] = suggestions.get("suggestionBudget")
        facts = dict(merged.get("phraseFacts") or {})
        facts["suggestions"] = (suggestions.get("phraseFacts") or {}).get("options")
        merged["phraseFacts"] = facts
        wm = WorkingMemory.model_validate(merged["workingMemory"])
        other = WorkingMemory.model_validate(suggestions["workingMemory"])
        wm.lastSuggestionOptions = other.lastSuggestionOptions
        merged["workingMemory"] = wm.model_dump(mode="json")
        if proposals:
            merged["memoryProposals"] = [p.model_dump(mode="json") for p in proposals]
        return merged
    if primary:
        if proposals and not primary.get("memoryProposals"):
            primary["memoryProposals"] = [p.model_dump(mode="json") for p in proposals]
        return primary
    if suggestions:
        if proposals and not suggestions.get("memoryProposals"):
            suggestions["memoryProposals"] = [p.model_dump(mode="json") for p in proposals]
        return suggestions
    if proposals:
        return _chat(req, memory, {"memory": [p.model_dump(mode="json") for p in proposals]}, proposals=proposals)
    return _chat(req, memory, {"reason": "no tool result"})
