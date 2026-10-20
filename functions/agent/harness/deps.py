"""Injectable search, USDA measures, and clock for the resolve pipeline."""

from __future__ import annotations

import time
from typing import Any, Callable

from schemas import InterpretMealRequest

_overrides: dict[str, Any] = {}


def set_overrides(**kwargs: Any) -> None:
    _overrides.clear()
    _overrides.update({k: v for k, v in kwargs.items() if v is not None})


def clear_overrides() -> None:
    _overrides.clear()


def _default_search(req: InterpretMealRequest) -> Callable[..., dict[str, Any]]:
    from agent.harness.search.food_search import search_foods

    def search(query: str, *, include_usda: bool = True) -> dict[str, Any]:
        return search_foods(req, query, include_usda=include_usda)

    return search


def _default_fetch(food_id: str) -> list[Any]:
    from agent.harness.search.usda import fetch_fdc_measures

    return fetch_fdc_measures(food_id)


def resolve_deps(req: InterpretMealRequest) -> dict[str, Any]:
    search = _overrides.get("search") or _default_search(req)
    fetch = _overrides.get("fetch_measures") or _default_fetch
    clock = _overrides.get("clock") or time.monotonic
    return {
        "search": search,
        "fetch_measures": fetch,
        "clock": clock,
    }
