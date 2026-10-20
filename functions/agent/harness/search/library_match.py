"""Strict library name match — prefer explicit titles, never broad staple overfit."""

from __future__ import annotations

import re
from typing import Iterable

from schemas import FoodHit, HouseholdMeasure, LibraryItemRef, MacroTotals

_STOP = {"a", "an", "the", "of", "and", "with", "my"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", _norm(text)) if t not in _STOP and len(t) > 1]


def library_name_match(query: str, name: str) -> bool:
    """True only for deliberate library picks — not 'chicken' → 'Sunday Chicken Feast'."""
    q = _norm(query)
    n = _norm(name)
    if not q or not n:
        return False
    if q == n:
        return True
    q_toks = _tokens(q)
    n_toks = _tokens(n)
    if not q_toks or not n_toks:
        return False
    # Broad single-token staples must not latch onto multi-word library titles.
    if len(q_toks) == 1 and len(n_toks) > 1:
        return False
    # All query tokens must appear in the library name (user named their item).
    if not all(t in n_toks for t in q_toks):
        return False
    # Library title shouldn't be much longer than the query (avoid loose containment).
    if len(n_toks) > len(q_toks) + 1:
        return False
    return True


def _per100g_from_serving(item: LibraryItemRef) -> MacroTotals:
    serving = max(float(item.servingGrams or 100), 1.0)
    factor = 100.0 / serving
    return MacroTotals(
        calories=float(item.calories) * factor,
        proteinG=float(item.proteinG) * factor,
        carbsG=float(item.carbsG) * factor,
        fatG=float(item.fatG) * factor,
    )


def to_food_hit(item: LibraryItemRef) -> FoodHit:
    serving = max(float(item.servingGrams or 100), 1.0)
    return FoodHit(
        foodId=f"library_{item.id}",
        displayName=item.name,
        source="library",
        per100g=_per100g_from_serving(item),
        family=str(item.kind or "food"),
        measures=[HouseholdMeasure(id="serving", label="1 serving", grams=serving)],
    )


def match_library(query: str, items: Iterable[LibraryItemRef], *, limit: int = 3) -> list[FoodHit]:
    hits: list[FoodHit] = []
    for item in items or []:
        if library_name_match(query, item.name):
            hits.append(to_food_hit(item))
        if len(hits) >= limit:
            break
    return hits
