"""Injectable search, web nutrition, and clock for the resolve pipeline."""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Optional

from schemas import InterpretMealRequest

_overrides: dict[str, Any] = {}


def set_overrides(**kwargs: Any) -> None:
    _overrides.clear()
    _overrides.update({k: v for k, v in kwargs.items() if v is not None})


def clear_overrides() -> None:
    _overrides.clear()


def _default_search(req: InterpretMealRequest) -> Callable[[str], dict[str, Any]]:
    from agent.harness.food_search import search_foods

    def search(query: str) -> dict[str, Any]:
        return search_foods(req, query)

    return search


def _default_fetch(food_id: str) -> list[Any]:
    from agent.harness.usda import fetch_fdc_measures

    return fetch_fdc_measures(food_id)


def _default_web(query: str) -> Optional[dict[str, Any]]:
    if os.environ.get("CAPY_MOCK_AGENT") == "1" and "web" not in _overrides:
        return None
    from agent.harness.web_nutrition import lookup_web_nutrition

    return lookup_web_nutrition(query)


def resolve_deps(req: InterpretMealRequest) -> dict[str, Any]:
    search = _overrides.get("search") or _default_search(req)
    fetch = _overrides.get("fetch_measures") or _default_fetch
    web = _overrides.get("web") or _default_web
    clock = _overrides.get("clock") or time.monotonic
    return {
        "search": search,
        "fetch_measures": fetch,
        "web": web,
        "clock": clock,
    }
