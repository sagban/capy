"""Embedded seed catalog for Functions (mirrors capy/Resources/SeedFoods.json)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from schemas import FoodHit, MacroTotals

_SEED_CANDIDATES = [
    Path(__file__).resolve().parent / "seed" / "SeedFoods.json",
    Path(__file__).resolve().parent.parent / "capy" / "Resources" / "SeedFoods.json",
    Path(__file__).resolve().parent.parent / "docs" / "seed" / "SeedFoods.draft.json",
]


@lru_cache(maxsize=1)
def load_seed() -> dict:
    for path in _SEED_CANDIDATES:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {"version": 1, "foods": [], "composites": [], "templates": []}


def all_food_hits() -> list[FoodHit]:
    seed = load_seed()
    hits: list[FoodHit] = []
    by_id: dict[str, FoodHit] = {}
    for food in seed.get("foods", []):
        per = food["per100g"]
        hit = FoodHit(
            foodId=food["id"],
            displayName=food["name"],
            source="seed",
            per100g=MacroTotals(**per),
            family=food.get("family", ""),
        )
        hits.append(hit)
        by_id[hit.foodId] = hit

    for composite in seed.get("composites", []):
        totals = MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
        grams_total = 0.0
        for component in composite.get("components", []):
            base = by_id.get(component["foodId"])
            if not base:
                continue
            g = float(component["grams"])
            factor = g / 100.0
            totals = MacroTotals(
                calories=totals.calories + base.per100g.calories * factor,
                proteinG=totals.proteinG + base.per100g.proteinG * factor,
                carbsG=totals.carbsG + base.per100g.carbsG * factor,
                fatG=totals.fatG + base.per100g.fatG * factor,
            )
            grams_total += g
        if grams_total > 0:
            f = 100.0 / grams_total
            per100 = MacroTotals(
                calories=totals.calories * f,
                proteinG=totals.proteinG * f,
                carbsG=totals.carbsG * f,
                fatG=totals.fatG * f,
            )
        else:
            per100 = MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
        hit = FoodHit(
            foodId=composite["id"],
            displayName=composite["name"],
            source="seed",
            per100g=per100,
            family="composite",
        )
        hits.append(hit)
        by_id[hit.foodId] = hit
    return hits


def search_seed(query: str, limit: int = 10) -> list[FoodHit]:
    q = query.strip().lower()
    if not q:
        return all_food_hits()[:limit]
    seed = load_seed()
    alias_map: dict[str, list[str]] = {
        f["id"]: [a.lower() for a in f.get("aliases", [])] for f in seed.get("foods", [])
    }
    scored: list[tuple[int, FoodHit]] = []
    for hit in all_food_hits():
        name = hit.displayName.lower()
        aliases = alias_map.get(hit.foodId, [])
        if q in name or any(q in a for a in aliases) or q in hit.family.lower():
            score = 0 if name.startswith(q) else 1
            scored.append((score, hit))
    scored.sort(key=lambda x: (x[0], x[1].displayName))
    return [h for _, h in scored[:limit]]


def get_food(food_id: str) -> FoodHit | None:
    for hit in all_food_hits():
        if hit.foodId == food_id:
            return hit
    return None


def templates() -> list[dict]:
    return list(load_seed().get("templates", []))
