"""USDA FoodData Central client — fetch pool; ranking lives in food_search."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from agent.harness.food_corpus_store import (
    corpus_store_enabled,
    get_search_slice,
    put_search_slice,
    slice_key_for_data_types,
)
from schemas import FoodHit, HouseholdMeasure, MacroTotals

FDC_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"

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


def _api_key(explicit: Optional[str]) -> str:
    return (
        explicit
        or os.environ.get("USDA_FDC_API_KEY")
        or os.environ.get("USDA_API_KEY")
        or ""
    )


def _fdc_search_live(
    query: str,
    *,
    data_types: list[str],
    page_size: int,
    api_key: str,
) -> list[dict[str, Any]]:
    payload = {
        "query": query,
        "pageSize": page_size,
        "dataType": data_types,
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(f"{FDC_SEARCH}?api_key={api_key}", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []
    return list(data.get("foods") or [])


def _fdc_search(
    query: str,
    *,
    data_types: list[str],
    page_size: int,
    api_key: str,
) -> list[dict[str, Any]]:
    slice_key = slice_key_for_data_types(data_types)
    if corpus_store_enabled():
        cached = get_search_slice(query, slice_key, page_size)
        if cached is not None:
            return cached

    foods = _fdc_search_live(
        query,
        data_types=data_types,
        page_size=page_size,
        api_key=api_key,
    )
    if corpus_store_enabled():
        put_search_slice(query, slice_key, page_size, foods)
    return foods


def _measures_from_food(food: dict[str, Any]) -> list[HouseholdMeasure]:
    measures: list[HouseholdMeasure] = []
    household = str(food.get("householdServingFullText") or "").strip()
    try:
        serving_g = float(food.get("servingSize") or 0)
    except (TypeError, ValueError):
        serving_g = 0.0
    if serving_g > 0:
        label = household or f"{serving_g:g} g serving"
        measures.append(HouseholdMeasure(id="serving", label=label, grams=serving_g))
    for index, raw in enumerate(food.get("foodMeasures") or []):
        if not isinstance(raw, dict):
            continue
        try:
            grams = float(raw.get("gramWeight") or 0)
        except (TypeError, ValueError):
            continue
        if grams <= 0:
            continue
        text = str(raw.get("disseminationText") or raw.get("modifier") or "").strip()
        if not text:
            text = f"{grams:g} g"
        measures.append(HouseholdMeasure(id=f"m{index}", label=text, grams=grams))
    return measures


def _to_hit(food: dict[str, Any]) -> Optional[FoodHit]:
    fdc_id = food.get("fdcId")
    if fdc_id is None:
        return None
    name = (food.get("description") or f"USDA {fdc_id}").strip()
    brand = (food.get("brandOwner") or food.get("brandName") or "").strip()
    data_type = (food.get("dataType") or "").lower()
    source = "usda_branded" if "branded" in data_type else "usda"
    if brand and brand.lower() not in name.lower():
        name = f"{name} — {brand}"
    per100 = MacroTotals(
        calories=_nutrient_value(food, _NUTRIENT_KCAL),
        proteinG=_nutrient_value(food, _NUTRIENT_PROTEIN),
        carbsG=_nutrient_value(food, _NUTRIENT_CARBS),
        fatG=_nutrient_value(food, _NUTRIENT_FAT),
    )
    if per100.calories <= 0 and per100.proteinG <= 0:
        return None
    return FoodHit(
        foodId=f"usda_{fdc_id}",
        displayName=name,
        source=source,
        per100g=per100,
        family="",
        measures=_measures_from_food(food),
    )


def search_usda_pool(query: str, limit: int = 40, api_key: Optional[str] = None) -> list[FoodHit]:
    """Fetch Branded + Foundation/SR Legacy pools (unranked beyond FDC order)."""
    key = _api_key(api_key)
    if not key or not query.strip():
        return []

    page = max(20, min(limit, 50))
    branded_raw = _fdc_search(
        query, data_types=["Branded"], page_size=page, api_key=key
    )
    other_raw = _fdc_search(
        query,
        data_types=["Foundation", "SR Legacy"],
        page_size=page,
        api_key=key,
    )
    survey_raw = _fdc_search(
        query,
        data_types=["Survey (FNDDS)"],
        page_size=page,
        api_key=key,
    )

    hits: list[FoodHit] = []
    seen: set[str] = set()
    for food in branded_raw + other_raw + survey_raw:
        hit = _to_hit(food)
        if hit is None or hit.foodId in seen:
            continue
        seen.add(hit.foodId)
        hits.append(hit)
        if len(hits) >= limit:
            break
    return hits


def fetch_fdc_measures(food_id: str, api_key: Optional[str] = None) -> list[HouseholdMeasure]:
    """One FDC details call when search did not include household measures."""
    key = _api_key(api_key)
    raw_id = str(food_id or "")
    if raw_id.startswith("usda_"):
        raw_id = raw_id[len("usda_") :]
    if not key or not raw_id.isdigit():
        return []
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"https://api.nal.usda.gov/fdc/v1/food/{raw_id}", params={"api_key": key})
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    return _measures_from_food(data)


def search_usda(query: str, limit: int = 5, api_key: Optional[str] = None) -> list[FoodHit]:
    """Back-compat thin wrapper — prefer food_search.search_foods for product ranking."""
    return search_usda_pool(query, limit=max(limit, 20), api_key=api_key)[:limit]
