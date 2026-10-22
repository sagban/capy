"""Catalog lookup and offline ranking of a caller-supplied pool."""

from __future__ import annotations

from agent.tools.lookups import search_catalog
from agent.tools.search.catalog import search_seed
from agent.tools.search.food_search import rank_candidates
from schemas import FoodHit, MacroTotals, request_from_dict


def _req(**kwargs):
    base = {
        "utterance": "x",
        "timezone": "UTC",
        "dayKey": "2026-10-12",
        "conversation": {"summary": "", "recentTurns": [], "workingMemory": None},
        "diaryContext": {
            "today": [],
            "previousDays": [],
            "remaining": {"calories": 2000, "proteinG": 150, "carbsG": 200, "fatG": 70},
        },
        "preferenceContext": {"likes": [], "dislikes": [], "allergies": [], "diets": []},
        "longTermMemory": [],
        "context": {"assistanceLevel": "fullAssist"},
        "memorySnapshot": {
            "preferences": [],
            "dislikes": [],
            "allergies": [],
            "diets": [],
            "regularTemplateIds": [],
            "recentCorrections": [],
        },
    }
    base.update(kwargs)
    return request_from_dict(base)


def _hit(fid: str, name: str, source: str = "usda") -> FoodHit:
    return FoodHit(
        foodId=fid,
        displayName=name,
        source=source,
        per100g=MacroTotals(calories=100, proteinG=10, carbsG=10, fatG=2),
        family="",
    )


def test_unresolved_short_token_forces_web():
    """User typed ON — no hit contains 'on' → low confidence, suggest web."""
    req = _req()
    hits = [
        _hit("usda_1", "Beverages, Protein powder whey based"),
        _hit("usda_2", "VANILLA WHEY PROTEIN POWDER — Publix"),
    ]
    ranked = rank_candidates(hits, "ON whey protein", req)
    assert ranked[0].unexplained
    assert "on" in ranked[0].unexplained


def test_full_label_query_ranks_optimum():
    req = _req()
    hits = [
        _hit("usda_1", "Beverages, Protein powder whey based"),
        _hit(
            "usda_2",
            "GOLD STANDARD 100% WHEY PROTEIN POWDER DRINK MIX — Optimum Nutrition, Inc.",
            "usda_branded",
        ),
        _hit("usda_3", "VANILLA WHEY PROTEIN POWDER — Publix", "usda_branded"),
    ]
    ranked = rank_candidates(hits, "Optimum Nutrition Gold Standard whey", req)
    assert "optimum" in ranked[0].hit.displayName.lower()
    assert not ranked[0].unexplained


def test_personalization_boosts_today_log():
    req = _req(
        diaryContext={
            "today": [{"name": "Gold Standard whey", "mealSlot": "snack", "grams": 64}],
            "previousDays": [],
            "remaining": {"calories": 1800, "proteinG": 120, "carbsG": 180, "fatG": 60},
        }
    )
    hits = [
        _hit("a", "Whey protein isolate"),
        _hit("b", "Gold Standard whey — Optimum Nutrition, Inc.", "usda_branded"),
    ]
    ranked = rank_candidates(hits, "whey", req)
    assert ranked[0].hit.foodId == "b"


def test_search_catalog_rice_is_seed_staple():
    result = search_catalog("rice", limit=8)
    hits = result["hits"]
    assert hits
    assert hits[0]["displayName"].lower().startswith("rice")
    assert result["source"] == "catalog"
    seed = search_seed("rice", limit=8)
    assert [hit["foodId"] for hit in hits] == [hit.foodId for hit in seed]


def test_search_catalog_empty_query_is_rejected():
    from pydantic import ValidationError

    from agent.tools.registry import SearchCatalogArgs

    try:
        SearchCatalogArgs(query="")
    except ValidationError:
        return
    raise AssertionError("empty catalog query should be rejected")
