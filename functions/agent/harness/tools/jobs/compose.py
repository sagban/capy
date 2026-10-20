"""compose_suggestions tool executor."""

from __future__ import annotations

import re
from typing import Any, Optional

from agent.harness.diets import diets_for, item_breaks_diet
from agent.harness.meal_budget import fit_label, slot_budget
from agent.harness.portions import suggestion_portion
from agent.harness.resolve import pick_for_suggestion, resolve_many
from agent.harness.tools.common import (
    base,
    blank_memory,
    chat,
    deps_deadline,
    scale,
)
from schemas import (
    InterpretMealRequest,
    ItemDraft,
    MacroTotals,
    MealIntent,
    MemoryProposal,
    SuggestionOption,
    SuggestionOptionItem,
    WorkingMemory,
)

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
    venue: str | None = None,
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
    default_venue = (venue or "").strip() or None
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
            brand = (raw.get("brandOrVenue") or default_venue or None)
            if isinstance(brand, str):
                brand = brand.strip() or None
            payload = {
                "foodQuery": str(raw.get("foodQuery") or ""),
                "quantity": float(raw["quantity"]),
                "unit": str(raw.get("unit")),
                "brandOrVenue": brand,
                "aliases": list(raw.get("aliases") or []),
                "portionMacros": raw.get("portionMacros"),
                "servingGrams": raw.get("servingGrams"),
                "citationUrl": raw.get("citationUrl"),
                "displayName": raw.get("displayName"),
            }
            item_drafts.append(ItemDraft.model_validate(payload))
        if missing_amount or any(not item.foodQuery for item in item_drafts):
            dropped.append(f"{title}: missing amount")
            continue
        results = resolve_many(
            item_drafts,
            search=deps["search"],
            fetch_measures=deps["fetch_measures"],
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
            reasons = sorted({r.reason for r in results if r.reason})
            suffix = f" ({', '.join(reasons)})" if reasons else ""
            dropped.append(f"{title}: unresolved{suffix}")
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
            # Menu-cited portions are already sized — don't cap a 16 oz latte to "3 servings".
            if item.source in {"web", "estimate"}:
                grams, label, condiment = item.grams, item.portionLabel, False
            else:
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


