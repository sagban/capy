"""ReAct harness goldens — CAPY_MOCK_AGENT=1 (see conftest)."""

from __future__ import annotations

import os

from agent.harness.catalog import get_food
from agent.harness.food_search import search_foods
from agent.graph import run_interpret
from agent.harness.messaging import GRACEFUL_FAILURE, sanitize_assistant_message
from schemas import request_from_dict


def _base_payload(**overrides):
    payload = {
        "utterance": "I had rice and dal",
        "timezone": "America/Chicago",
        "dayKey": "2026-10-12",
        "preferenceContext": {
            "likes": [],
            "dislikes": [],
            "allergies": [],
            "diets": [],
        },
        "diaryContext": {
            "today": [],
            "previousDays": [],
            "remaining": {
                "calories": 820,
                "proteinG": 60,
                "carbsG": 90,
                "fatG": 25,
            },
            "remainingSource": "clientComputed",
        },
        "longTermMemory": [],
        "conversation": {"summary": "", "recentTurns": [], "workingMemory": None},
        "context": {"assistanceLevel": "fullAssist", "lastIntent": None},
    }
    payload.update(overrides)
    return payload


def test_mock_agent_enabled():
    assert os.environ.get("CAPY_MOCK_AGENT") == "1"


def test_greeting_is_not_log_meal():
    from agent.harness.mock_turn import push_mock_turns

    push_mock_turns([{"kind": "text", "text": "Hello! How can I help you?"}])
    out = run_interpret(_base_payload(utterance="Hey"))
    assert out["intent"] == "unknown"
    assert not out.get("candidates")
    assert out.get("pendingAction") is None
    assert out["assistantMessage"] == "Hello! How can I help you?"


def test_search_food_rice_ranks_staple():
    req = request_from_dict(_base_payload())
    result = search_foods(req, "rice", limit=8)
    assert result["cache"] == "hit"
    names = [r["displayName"].lower() for r in result["results"]]
    assert names
    assert names[0].startswith("rice")
    assert "babyfood" not in names[0]
    assert any("cooked" in n for n in names[:3])


def test_search_hi_does_not_match_chicken():
    req = request_from_dict(_base_payload())
    result = search_foods(req, "hi", limit=8)
    assert result["results"] == [] or result["cache"] == "miss"


def test_search_food_seed_hit():
    req = request_from_dict(_base_payload())
    result = search_foods(req, "paneer")
    assert result["cache"] in {"hit", "usda"}
    assert any(r["foodId"] == "seed_paneer" for r in result["results"])


def test_sanitize_strips_tech_and_ids():
    dirty = "Vertex Gemini 404 usda_168878 https://example.com harness error (503)"
    clean = sanitize_assistant_message(dirty)
    assert "vertex" not in clean.lower()
    assert "usda_" not in clean.lower()
    assert "503" not in clean
    assert "http" not in clean.lower()


def test_fail_closed_message_has_no_stack():
    assert "vertex" not in GRACEFUL_FAILURE.lower()
    assert "firebase" not in GRACEFUL_FAILURE.lower()


def test_scale_portion_from_catalog():
    req = request_from_dict(_base_payload())
    search = search_foods(req, "rice", limit=1)
    food = get_food(search["results"][0]["foodId"])
    assert food is not None
    calories = round(food.per100g.calories * 2.0, 2)
    assert calories > 0


def test_chat_text_is_not_a_tool_outcome():
    from agent.harness.mock_turn import push_mock_turns

    push_mock_turns([{"kind": "text", "text": "Nothing logged yet."}])
    out = run_interpret(_base_payload(utterance="what did I have"))
    assert out["pendingAction"] is None
    assert out["intent"] == "unknown"
