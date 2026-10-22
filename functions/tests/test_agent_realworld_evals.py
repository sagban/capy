"""Real-world agent evals — scripted tool calls, assert user-visible outcomes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.graph import reset_graph, run_interpret
from agent.harness.mock_turn import push_mock_turns
from agent.harness.outcomes import normalize_outcome
from agent.tools.lookups import set_lookup_overrides

_FIXTURE = Path(__file__).parent / "fixtures" / "agent_realworld_evals.json"

EGG = {
    "foodId": "seed_egg",
    "displayName": "Egg",
    "source": "seed",
    "per100g": {"calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11},
    "family": "egg",
    "measures": [{"id": "large", "label": "1 large", "grams": 50}],
}
CHICKEN = {
    "foodId": "usda_chicken_breast",
    "displayName": "Chicken breast, grilled",
    "source": "usda",
    "per100g": {"calories": 165, "proteinG": 31, "carbsG": 0, "fatG": 3.6},
    "family": "poultry",
    "measures": [{"id": "serving", "label": "1 serving", "grams": 100}],
}


def setup_function(_fn):
    reset_graph()


def _load_cases() -> list[dict]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return list(data["cases"])


def _payload(case: dict, utterance: str | None = None) -> dict:
    return {
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


def _catalog(query: str, limit: int = 10) -> dict:
    del limit
    q = (query or "").lower()
    if "chicken" in q:
        return {"source": "catalog", "hits": [CHICKEN]}
    if "egg" in q:
        return {"source": "catalog", "hits": [EGG]}
    return {"source": "catalog", "hits": []}


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
    set_lookup_overrides(catalog=_catalog)
    push_mock_turns(case["mock_turns"])
    out = run_interpret(_payload(case))
    normalize_outcome(out)
    _assert_expect(out, case["expect"], case_id=case["id"])

    follow = case.get("followUp")
    if not follow:
        return
    push_mock_turns(follow["mock_turns"])
    second = run_interpret(
        _payload(case, utterance=follow["utterance"])
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
