"""Suggestion cards from hits and gram amounts already fetched in this turn."""

from __future__ import annotations

from typing import Any

from schemas import MacroTotals, SuggestionOption, SuggestionOptionItem


def _scale(per: dict[str, Any], grams: float) -> dict[str, float]:
    factor = float(grams) / 100.0
    return {
        "calories": round(float(per.get("calories") or 0) * factor, 2),
        "proteinG": round(float(per.get("proteinG") or 0) * factor, 2),
        "carbsG": round(float(per.get("carbsG") or 0) * factor, 2),
        "fatG": round(float(per.get("fatG") or 0) * factor, 2),
    }


def _match_hit(hits: list[dict[str, Any]], measures: list[Any]) -> dict[str, Any] | None:
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]
    wanted = measures or []
    for hit in hits:
        if (hit.get("measures") or []) == wanted:
            return hit
    return hits[0]


def suggestion_options(trace: list[dict[str, Any]], remaining: MacroTotals) -> list[SuggestionOption]:
    last_hits: list[dict[str, Any]] = []
    chosen: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for step in trace:
        name = step.get("name")
        result = step.get("result") if isinstance(step.get("result"), dict) else {}
        if name in {"search_catalog", "search_usda", "search_library"}:
            last_hits = [hit for hit in (result.get("hits") or []) if isinstance(hit, dict)]
        elif name == "lookup_barcode" and result.get("found"):
            last_hits = [result]
        elif name == "portion_to_grams" and not result.get("unmapped") and result.get("grams"):
            hit = _match_hit(last_hits, (step.get("arguments") or {}).get("measures") or [])
            per = (hit or {}).get("per100g")
            if hit and isinstance(per, dict):
                chosen.append((hit, result))
    if not chosen:
        return []
    items: list[SuggestionOptionItem] = []
    totals = {"calories": 0.0, "proteinG": 0.0, "carbsG": 0.0, "fatG": 0.0}
    for hit, portion in chosen:
        grams = float(portion["grams"])
        scaled = _scale(hit["per100g"], grams)
        for key in totals:
            totals[key] = round(totals[key] + scaled[key], 2)
        items.append(
            SuggestionOptionItem(
                foodId=str(hit.get("foodId") or "hit"),
                displayName=str(hit.get("displayName") or "Food"),
                grams=grams,
                source=str(hit.get("source") or ""),
                per100g=MacroTotals.model_validate(hit["per100g"]),
                portionLabel=portion.get("label"),
                family=str(hit.get("family") or ""),
            )
        )
    fit = "over" if totals["calories"] > float(remaining.calories) + 0.5 else "within"
    title = items[0].displayName if len(items) == 1 else " and ".join(item.displayName for item in items[:3])
    return [
        SuggestionOption(
            id="s1",
            title=title,
            items=items,
            totals=MacroTotals.model_validate(totals),
            fit=fit,
        )
    ]
