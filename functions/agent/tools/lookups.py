"""Stateless food lookups. Each one returns hits and stops."""

from __future__ import annotations

from typing import Any

from agent.tools.search.library_match import match_library
from schemas import LibraryItemRef

_overrides: dict[str, Any] = {}


def set_lookup_overrides(**kwargs: Any) -> None:
    """Test hook. Production leaves this empty."""
    _overrides.clear()
    _overrides.update({k: v for k, v in kwargs.items() if v is not None})


def clear_lookup_overrides() -> None:
    _overrides.clear()


def _hits(source: str, hits: list[Any]) -> dict[str, Any]:
    return {"source": source, "hits": [hit.model_dump(mode="json") for hit in hits]}


def search_catalog(query: str, limit: int = 10) -> dict[str, Any]:
    override = _overrides.get("catalog")
    if override is not None:
        return override(query, limit)
    from agent.tools.search.catalog import search_seed

    return _hits("catalog", search_seed(query, limit=limit))


def search_usda(query: str, limit: int = 8) -> dict[str, Any]:
    override = _overrides.get("usda")
    if override is not None:
        return override(query, limit)
    from agent.tools.search.usda import search_usda_pool

    return _hits("usda", search_usda_pool(query, limit=limit))


def search_library(query: str, items: list[Any], limit: int = 3) -> dict[str, Any]:
    override = _overrides.get("library")
    if override is not None:
        return override(query, items, limit)
    refs: list[LibraryItemRef] = []
    for row in items or []:
        if isinstance(row, LibraryItemRef):
            refs.append(row)
        elif isinstance(row, dict):
            refs.append(LibraryItemRef.model_validate(row))
    return _hits("library", match_library(query, refs, limit=limit))


def lookup_barcode(gtin: str) -> dict[str, Any]:
    override = _overrides.get("barcode")
    if override is not None:
        return override(gtin)
    from agent.tools.search.open_food_facts import lookup_barcode as run

    return run(gtin)
