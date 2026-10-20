"""Real-world agent evals — scripted tool calls, injected search, assert user-visible outcomes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.graph import reset_graph, run_interpret
from agent.harness.deps import set_overrides
from agent.harness.mock_turn import push_mock_turns
from agent.harness.outcomes import normalize_outcome
from agent.harness.tools import jobs
from schemas import InterpretMealRequest, request_from_dict

_FIXTURE = Path(__file__).parent / "fixtures" / "agent_realworld_evals.json"


def setup_function(_fn):
    reset_graph()


def _load_cases() -> list[dict]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return list(data["cases"])


def _payload(case: dict, utterance: str | None = None) -> dict:
    base = {
        "utterance": utterance if utterance is not None else case["utterance"],
        "timezone": "America/Chicago",
        "dayKey": "2026-10-19",
        "preferenceContext": {"likes": [], "dislikes": [], "allergies": [], "diets": []},
        "diaryContext": {
            "today": [],
            "previousDays": [],
            "remaining": {"calories": 1600, "proteinG": 90, "carbsG": 150, "fatG": 50},
        },
        "longTermMemory": [],
        "conversation": {"summary": "", "recentTurns": [], "workingMemory": None},
        "context": {"assistanceLevel": "fullAssist", "responseStyle": "balanced", "lastIntent": None},
        "libraryContext": case.get("libraryContext") or [],
    }
    return base


def _miss():
    return {"results": [], "candidatesForClarify": [], "confidence": "none", "sources": []}


def _pack_hit(hit) -> dict:
    return {
        "foodId": hit.foodId,
        "displayName": hit.displayName,
        "source": hit.source,
        "per100g": hit.per100g.model_dump(),
        "family": hit.family,
        "measures": [m.model_dump() for m in (hit.measures or [])],
    }


def _catalog_stub(query: str, *, include_usda: bool = True) -> dict:
    """Only hit when the query clearly names that food — never egg-for-everything."""
    q = (query or "").lower()
    if "chicken" in q:
        row = {
            "foodId": "usda_chicken_breast",
            "displayName": "Chicken breast, grilled",
            "source": "usda",
            "per100g": {"calories": 165, "proteinG": 31, "carbsG": 0, "fatG": 3.6},
            "family": "poultry",
            "measures": [{"id": "serving", "label": "1 serving", "grams": 100}],
        }
        return {"results": [row], "candidatesForClarify": [row], "confidence": "high", "sources": ["usda"]}
    if "liquid" in q and "egg" in q:
        row = {
            "foodId": "usda_egg_white",
            "displayName": "Egg white, raw",
            "source": "usda",
            "per100g": {"calories": 52, "proteinG": 11, "carbsG": 0.7, "fatG": 0.2},
            "family": "egg",
            "measures": [],
        }
        return {"results": [row], "candidatesForClarify": [row], "confidence": "high", "sources": ["usda"]}
    if "egg" in q:
        row = {
            "foodId": "seed_egg",
            "displayName": "Egg",
            "source": "seed",
            "per100g": {"calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11},
            "family": "egg",
            "measures": [{"id": "m0", "label": "1 large", "grams": 50}],
        }
        return {"results": [row], "candidatesForClarify": [row], "confidence": "high", "sources": ["seed"]}
    _ = include_usda
    return _miss()


def _install_search(library_context: list | None = None):
    """Stub catalog/USDA but still apply strict library matching (overrides replace search_foods)."""
    from agent.harness.search.library_match import match_library
    from schemas import LibraryItemRef

    items = [LibraryItemRef.model_validate(row) for row in (library_context or [])]

    def search(query: str, *, include_usda: bool = True, **_kwargs):
        lib_hits = match_library(query, items, limit=3)
        if lib_hits:
            packed = [_pack_hit(h) for h in lib_hits]
            return {
                "results": packed,
                "candidatesForClarify": packed,
                "confidence": "high",
                "reason": "library_exact",
                "sources": ["library"],
            }
        return _catalog_stub(query, include_usda=include_usda)

    set_overrides(search=search, fetch_measures=lambda _fid: [])


def _rewrite_option_id(turns: list[dict], option_id: str) -> list[dict]:
    text = json.dumps(turns)
    text = text.replace("$firstOptionId", option_id)
    return json.loads(text)


def _assert_expect(out: dict, expect: dict, *, case_id: str) -> None:
    if "intent" in expect:
        assert out.get("intent") == expect["intent"], case_id
    if expect.get("notIntent"):
        assert out.get("intent") != expect["notIntent"], case_id
    options = out.get("suggestionOptions") or []
    if "minOptions" in expect:
        assert len(options) >= int(expect["minOptions"]), case_id
    if expect.get("optionSourcesAny"):
        sources = {
            str(item.get("source") or "")
            for opt in options
            for item in (opt.get("items") or [])
        }
        assert sources.intersection(set(expect["optionSourcesAny"])), (case_id, sources)
    pending = out.get("pendingAction")
    if "pendingAction" in expect:
        wanted = expect["pendingAction"]
        if wanted is None:
            assert pending is None, case_id
        else:
            assert pending and pending.get("type") == wanted, case_id
    if expect.get("pendingActionAny"):
        assert pending and pending.get("type") in expect["pendingActionAny"], case_id
    if expect.get("resolvedSources") is not None:
        items = (pending or {}).get("payload", {}).get("resolvedItems") or []
        sources = [str(i.get("source") or "") for i in items]
        assert sources == list(expect["resolvedSources"]), (case_id, sources)
    if expect.get("resolvedSourcesExclude"):
        items = (pending or {}).get("payload", {}).get("resolvedItems") or []
        sources = {str(i.get("source") or "") for i in items}
        for banned in expect["resolvedSourcesExclude"]:
            assert banned not in sources, (case_id, sources)
    if expect.get("resolvedNamesAny"):
        items = (pending or {}).get("payload", {}).get("resolvedItems") or []
        names = [str(i.get("displayName") or "") for i in items]
        assert any(n in names for n in expect["resolvedNamesAny"]), (case_id, names)
    msg = (out.get("assistantMessage") or "").lower()
    if expect.get("assistantContainsAny"):
        assert any(s.lower() in msg for s in expect["assistantContainsAny"]), (case_id, msg)


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_realworld_case(case: dict):
    _install_search(case.get("libraryContext") or [])
    push_mock_turns(case["mock_turns"])
    out = run_interpret(_payload(case))
    normalize_outcome(out)
    _assert_expect(out, case["expect"], case_id=case["id"])

    follow = case.get("followUp")
    if not follow:
        return
    option_id = (out.get("suggestionOptions") or [{}])[0].get("id")
    assert option_id, case["id"]
    turns = _rewrite_option_id(follow["mock_turns"], str(option_id))
    push_mock_turns(turns)
    second = run_interpret(
        _payload(
            case,
            utterance=follow["utterance"],
        )
        | {
            "conversation": {
                "summary": "",
                "recentTurns": [],
                "workingMemory": out.get("workingMemory"),
            }
        }
    )
    normalize_outcome(second)
    _assert_expect(second, follow["expect"], case_id=f"{case['id']}/followUp")


def test_venue_drop_reason_is_observably_venue_needs_citation():
    """Graph response drops phraseFacts; assert the tool outcome still carries dropped."""
    _install_search([])
    req = request_from_dict(_payload({"utterance": "x", "libraryContext": []}))
    assert isinstance(req, InterpretMealRequest)
    out = jobs.compose_suggestions(
        req,
        meal_slot=None,
        budget=None,
        drafts=[
            {
                "title": "Toast",
                "items": [
                    {
                        "foodQuery": "avocado toast special",
                        "quantity": 1,
                        "unit": "serving",
                        "brandOrVenue": "First Cup Coffee",
                    }
                ],
            }
        ],
    )
    facts = out.get("phraseFacts") or {}
    assert facts.get("reason") == "no suggestion survived"
    dropped = " ".join(facts.get("dropped") or [])
    assert "venue_needs_citation" in dropped
