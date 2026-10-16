"""Tool executors and one-turn merge."""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from agent.harness.diets import diets_for, item_breaks_diet
from agent.harness.meal_budget import fit_label, slot_budget
from agent.harness.portions import resolve_portion, suggestion_portion
from agent.harness.resolve import canonical_source, pick_for_suggestion, resolve_many
from agent.harness.tools.common import (
    apply_amount,
    base,
    blank_memory,
    chat,
    deps_deadline,
    diary_rows,
    item_results_from_resolved,
    pending,
    results_to_outcome,
    scale,
)
from schemas import (
    InterpretMealRequest,
    ItemDraft,
    MacroTotals,
    MealIntent,
    MemoryProposal,
    PendingActionPayload,
    PendingActionType,
    ResolvedItem,
    SuggestionOption,
    SuggestionOptionItem,
    WorkingMemory,
)


def resolve_meal(
    req: InterpretMealRequest,
    items: list[dict[str, Any]],
    *,
    memory: Optional[WorkingMemory] = None,
    proposals: Optional[list[MemoryProposal]] = None,
    correction: Optional[tuple[str, int, str]] = None,
) -> dict[str, Any]:
    memory = memory or blank_memory(req)
    proposals = proposals or []
    drafts = [ItemDraft.model_validate(item) for item in items]
    deps, deadline = deps_deadline(req)
    results = resolve_many(
        drafts,
        search=deps["search"],
        fetch_measures=deps["fetch_measures"],
        web=deps["web"],
        clock=deps["clock"],
        deadline=deadline,
    )
    return results_to_outcome(
        req,
        results,
        memory=memory,
        proposals=proposals,
        correction=correction,
    )


def edit_draft(req: InterpretMealRequest, ops: list[dict[str, Any]]) -> dict[str, Any]:
    memory = blank_memory(req)
    items = [item.model_copy(deep=True) for item in (memory.draftLog or [])]
    if not items and memory.resolveQueue is not None:
        items = [item.model_copy(deep=True) for item in memory.resolveQueue.resolved]
    added: list[ItemDraft] = []
    for op in ops or []:
        kind = str(op.get("op") or "")
        index = op.get("index")
        if kind == "remove":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return chat(req, memory, {"reason": "that item is not in the open log"})
            del items[index]
            continue
        if kind == "set_amount":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return chat(req, memory, {"reason": "that item is not in the open log"})
            updated = apply_amount(items[index], float(op.get("quantity") or 0), op.get("unit"))
            if updated is None:
                return chat(req, memory, {"reason": "need a unit for that amount", "food": items[index].displayName})
            items[index] = updated
            continue
        if kind == "add":
            added.append(ItemDraft.model_validate(op.get("item") or {}))
            continue
        if kind == "replace":
            if not isinstance(index, int) or not 0 <= index < len(items):
                return chat(req, memory, {"reason": "that item is not in the open log"})
            del items[index]
            added.append(ItemDraft.model_validate(op.get("item") or {}))
            continue
        return {"error": "bad_args", "message": f"unknown edit op {kind}"}

    resolved_results = item_results_from_resolved(items)
    if not added and not items:
        return chat(req, memory, {"reason": "the open log is empty"})
    if not added:
        memory.draftLog = items
        return results_to_outcome(req, resolved_results, memory=memory, proposals=[])

    deps, deadline = deps_deadline(req)
    tail = resolve_many(
        added,
        search=deps["search"],
        fetch_measures=deps["fetch_measures"],
        web=deps["web"],
        clock=deps["clock"],
        deadline=deadline,
    )
    return results_to_outcome(req, resolved_results + tail, memory=memory, proposals=[])


def log_from_suggestion(
    req: InterpretMealRequest,
    option_id: str,
    ops: list[dict[str, Any]] | None,
    memory: Optional[WorkingMemory] = None,
) -> dict[str, Any]:
    memory = memory or blank_memory(req)
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
    if ops:
        for op in ops:
            kind = str(op.get("op") or "")
            index = op.get("index")
            if kind == "set_amount" and isinstance(index, int) and 0 <= index < len(items):
                updated = apply_amount(items[index], float(op.get("quantity") or 0), op.get("unit"))
                if updated is None:
                    return chat(req, memory, {"reason": "need a unit for that amount", "food": items[index].displayName})
                items[index] = updated
            elif kind == "remove" and isinstance(index, int) and 0 <= index < len(items):
                del items[index]
    memory.draftLog = items
    return results_to_outcome(req, item_results_from_resolved(items), memory=memory, proposals=[])


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


def correct_entry(
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
        return resolve_meal(
            req,
            [item],
            memory=memory,
            correction=(entry_id, item_index, "replace"),
        )
    return {"error": "bad_args", "message": f"unknown correction op {op}"}


def fetch_menu(venue: str) -> dict[str, Any]:
    """Menu item names only. Digits in the grounded text are removed."""
    name = (venue or "").strip()
    if os.environ.get("CAPY_MOCK_AGENT") == "1":
        from agent.harness.deps import _overrides

        scripted = _overrides.get("menu")
        if isinstance(scripted, dict):
            return scripted
        return {"venue": name, "items": ""}
    from agent.harness.web_search import web_search

    raw = web_search(f"{name} menu items")
    chunks: list[str] = []
    for row in raw.get("results") or []:
        if isinstance(row, dict) and row.get("summary"):
            chunks.append(str(row["summary"]))
    text = re.sub(r"\d+(?:\.\d+)?", " ", " ".join(chunks))
    text = re.sub(r"\s+", " ", text).strip()
    return {"venue": name, "items": text[:1500]}


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


def compose_suggestions(
    req: InterpretMealRequest,
    *,
    meal_slot: str | None,
    budget: dict[str, Any] | None,
    appetite: str = "normal",
    drafts: list[dict[str, Any]],
    memory: Optional[WorkingMemory] = None,
    proposals: Optional[list[MemoryProposal]] = None,
) -> dict[str, Any]:
    memory = memory or blank_memory(req)
    proposals = proposals or []
    sized = slot_budget(req, meal_slot, budget, appetite=appetite)
    blocked = list(req.preferenceContext.allergies or []) + list(req.preferenceContext.dislikes or [])
    diets = diets_for(req, proposals)
    families = _today_families(req)
    deps, deadline = deps_deadline(req)
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
        resolved = []
        for result in results:
            item = pick_for_suggestion(result)
            if item is None:
                resolved = []
                break
            resolved.append(item)
        if not resolved:
            dropped.append(f"{title}: unresolved")
            continue
        if any(_token_conflict(item.displayName, item.family, blocked) for item in resolved):
            dropped.append(f"{title}: restriction")
            continue
        if any(item_breaks_diet(item.displayName, item.family, diets) for item in resolved):
            dropped.append(f"{title}: diet")
            continue
        if any(item.family and item.family.lower() in families for item in resolved):
            dropped.append(f"{title}: already eaten")
            continue
        sized_items = []
        condiment_only = True
        for item in resolved:
            grams, label, condiment = suggestion_portion(
                item.grams,
                kcal_per_100g=item.per100g.calories,
                family=item.family,
                measures=list(item.measures),
                portion_label=item.portionLabel,
            )
            if not condiment:
                condiment_only = False
            updated = item.model_copy(deep=True)
            updated.grams = round(grams, 2)
            updated.portionLabel = label
            sized_items.append(updated)
        if condiment_only:
            dropped.append(f"{title}: not a meal")
            continue
        resolved = sized_items
        totals = MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
        option_items: list[SuggestionOptionItem] = []
        for item in resolved:
            scaled = scale(item.per100g, item.grams)
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
        label = fit_label(
            totals.calories,
            totals.proteinG,
            sized,
            carbs_g=totals.carbsG,
            fat_g=totals.fatG,
        )
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
    budget_out: dict[str, float] = {"calories": float(sized["calories"] or 0)}
    for key in ("proteinG", "carbsG", "fatG"):
        if sized.get(key) is not None:
            budget_out[key] = float(sized[key])
    if not options:
        return chat(
            req,
            memory,
            {"reason": "no suggestion survived", "dropped": dropped, "budget": budget_out},
            proposals=proposals,
            budget=budget_out,
        )
    return base(
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


def run_calls(req: InterpretMealRequest, calls: list[dict[str, Any]]) -> dict[str, Any]:
    from agent.harness.tools.registry import parse_tool_args

    memory = blank_memory(req)
    ctx: dict[str, Any] = {"memory": memory, "proposals": []}
    primary: Optional[dict[str, Any]] = None
    suggestions: Optional[dict[str, Any]] = None
    menu: Optional[dict[str, Any]] = None
    for call in calls:
        parsed = parse_tool_args(str(call.get("name") or ""), call.get("arguments") or {})
        if isinstance(parsed, str):
            return {"error": "bad_args", "message": parsed}
        tool, arguments = parsed
        result = tool.invoke({**arguments, "ctx": {**ctx, "req": req}})
        kind = (tool.metadata or {}).get("kind")
        if kind == "lookup":
            menu = result if isinstance(result, dict) else None
            continue
        if kind == "memory":
            if isinstance(result, dict) and result.get("error"):
                return result
            continue
        if isinstance(result, dict) and result.get("error"):
            return result
        if kind == "suggestions":
            suggestions = result
        else:
            primary = result

    proposals: list[MemoryProposal] = ctx["proposals"]
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
        return chat(req, memory, {"memory": [p.model_dump(mode="json") for p in proposals]}, proposals=proposals)
    if menu:
        return chat(req, memory, {"venue": menu.get("venue"), "items": menu.get("items")})
    return chat(req, memory, {"reason": "no tool result"})
