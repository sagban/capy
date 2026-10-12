"""USDA FoodData Central Foundation / SR Legacy fallback client."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from schemas import FoodHit, MacroTotals

FDC_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"

# Nutrient numbers commonly used in FDC
_NUTRIENT_KCAL = {1008}
_NUTRIENT_PROTEIN = {1003}
_NUTRIENT_CARBS = {1005}
_NUTRIENT_FAT = {1004}


def _nutrient_value(food: dict[str, Any], ids: set[int]) -> float:
    for n in food.get("foodNutrients", []):
        nid = n.get("nutrientId") or n.get("nutrientNumber")
        try:
            nid_int = int(nid)
        except (TypeError, ValueError):
            continue
        if nid_int in ids:
            return float(n.get("value") or 0)
    return 0.0


def search_usda(query: str, limit: int = 5, api_key: Optional[str] = None) -> list[FoodHit]:
    key = (
        api_key
        or os.environ.get("USDA_FDC_API_KEY")
        or os.environ.get("USDA_API_KEY")
    )
    if not key or not query.strip():
        return []
    payload = {
        "query": query,
        "pageSize": limit,
        "dataType": ["Foundation", "SR Legacy"],
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(f"{FDC_SEARCH}?api_key={key}", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    hits: list[FoodHit] = []
    for food in data.get("foods", [])[:limit]:
        fdc_id = food.get("fdcId")
        if fdc_id is None:
            continue
        name = food.get("description") or f"USDA {fdc_id}"
        per100 = MacroTotals(
            calories=_nutrient_value(food, _NUTRIENT_KCAL),
            proteinG=_nutrient_value(food, _NUTRIENT_PROTEIN),
            carbsG=_nutrient_value(food, _NUTRIENT_CARBS),
            fatG=_nutrient_value(food, _NUTRIENT_FAT),
        )
        hits.append(
            FoodHit(
                foodId=f"usda_{fdc_id}",
                displayName=name,
                source="usda",
                per100g=per100,
                family="",
            )
        )
    return hits
