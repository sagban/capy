"""Golden eval suite for food_search — the ranking moat.

Loads fixtures/food_search_evals.json. Each case supplies a candidate pool
(no live USDA) and asserts top-id / confidence / web-escalation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.harness.food_search import (
    confidence_for,
    query_breadth,
    rank_candidates,
    search_foods,
)
from schemas import FoodHit, MacroTotals, request_from_dict

_FIXTURE = Path(__file__).parent / "fixtures" / "food_search_evals.json"


def _load_cases() -> list[dict]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return list(data["cases"])


def _hit(row: dict) -> FoodHit:
    return FoodHit(
        foodId=row["foodId"],
        displayName=row["displayName"],
        source=row.get("source") or "usda",
        per100g=MacroTotals(
            calories=float(row.get("calories", 100)),
            proteinG=float(row.get("proteinG", 10)),
            carbsG=float(row.get("carbsG", 10)),
            fatG=float(row.get("fatG", 2)),
        ),
        family=row.get("family") or "",
    )


def _req_from_case(case: dict):
    today = case.get("today") or []
    likes = case.get("likes") or []
    dislikes = case.get("dislikes") or []
    diets = case.get("diets") or []
    corrections = case.get("corrections") or []
    pending = case.get("pending_candidates") or []
    wm = None
    if pending:
        wm = {
            "pendingIntent": "clarify",
            "clarifyingQuestion": "which?",
            "candidates": pending,
            "pendingAction": None,
        }
    return request_from_dict(
        {
            "utterance": case["query"],
            "timezone": "UTC",
            "dayKey": "2026-10-12",
            "conversation": {
                "summary": "",
                "recentTurns": [],
                "workingMemory": wm,
            },
            "diaryContext": {
                "today": today,
                "previousDays": [],
                "remaining": {
                    "calories": 2000,
                    "proteinG": 150,
                    "carbsG": 200,
                    "fatG": 70,
                },
            },
            "preferenceContext": {
                "likes": likes,
                "dislikes": dislikes,
                "allergies": [],
                "diets": diets,
            },
            "longTermMemory": [],
            "context": {"assistanceLevel": "fullAssist"},
            "memorySnapshot": {
                "preferences": likes,
                "dislikes": dislikes,
                "allergies": [],
                "diets": diets,
                "regularTemplateIds": [],
                "recentCorrections": corrections,
            },
        }
    )


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_food_search_eval_case(case: dict, monkeypatch: pytest.MonkeyPatch):
    req = _req_from_case(case)
    query = case["query"]
    pool = [_hit(r) for r in case.get("pool") or []]

    if "expect_breadth" in case:
        assert query_breadth(query) == case["expect_breadth"]

    # Patch retrieval so evals stay offline and deterministic.
    monkeypatch.setattr(
        "agent.harness.food_search.search_seed",
        lambda q, limit=12: [h for h in pool if h.source == "seed"][:limit],
    )
    monkeypatch.setattr(
        "agent.harness.food_search.search_usda_pool",
        lambda q, limit=40: [h for h in pool if h.source != "seed"][:limit],
    )

    out = search_foods(req, query, limit=8)
    ranked = rank_candidates(pool, query, req) if pool else []

    if "expect_confidence" in case:
        assert out["confidence"] in case["expect_confidence"], (
            f"{case['id']}: confidence {out['confidence']} reason={out.get('reason')}"
        )

    if "expect_suggest_web" in case:
        assert out["suggestWebSearch"] is case["expect_suggest_web"], case["id"]

    if case.get("expect_results_empty"):
        assert out["results"] == [], (
            f"{case['id']}: expected empty results, got {[r['foodId'] for r in out['results']]}"
        )

    if "expect_top_id" in case and pool:
        # Prefer post-filter search_foods ordering when results are non-empty.
        surface = out.get("results") or out.get("candidatesForClarify") or []
        if surface and not case.get("expect_results_empty"):
            assert surface[0]["foodId"] == case["expect_top_id"], (
                f"{case['id']}: top={surface[0]['foodId']} "
                f"({surface[0]['displayName']}) conf={out.get('confidence')}"
            )
        else:
            assert ranked, f"{case['id']}: empty ranked"
            assert ranked[0].hit.foodId == case["expect_top_id"], (
                f"{case['id']}: top={ranked[0].hit.foodId} "
                f"({ranked[0].hit.displayName}) score={ranked[0].score:.1f}"
            )

    if "expect_not_top_substr" in case:
        surface = out.get("results") or out.get("candidatesForClarify") or []
        top_name = (surface[0]["displayName"] if surface else ranked[0].hit.displayName).lower()
        for sub in case["expect_not_top_substr"]:
            assert sub not in top_name, case["id"]

    if "expect_not_in_top_ids" in case:
        result_ids = [r["foodId"] for r in out.get("candidatesForClarify") or out.get("results") or []]
        for bad in case["expect_not_in_top_ids"]:
            assert bad not in result_ids, f"{case['id']}: {bad} should be filtered"

    if "expect_top_has_unexplained" in case and ranked:
        for tok in case["expect_top_has_unexplained"]:
            assert tok in ranked[0].unexplained, (
                f"{case['id']}: expected unexplained {tok}, got {ranked[0].unexplained}"
            )


def test_eval_fixture_has_significant_coverage():
    cases = _load_cases()
    assert len(cases) >= 25
    ids = {c["id"] for c in cases}
    # Must cover the moat buckets.
    assert any(i.startswith("staple_") for i in ids)
    assert any("brand" in i for i in ids)
    assert any(i.startswith("personal_") for i in ids)
    assert any(i.startswith("noise_") for i in ids)


def test_confidence_for_empty():
    conf, web, reason = confidence_for([], "rice")
    assert conf == "none" and web and reason == "no_hits"
