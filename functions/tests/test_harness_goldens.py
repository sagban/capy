"""Emulator / unit goldens for tools + multi-turn memory (#38)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graph import run_interpret  # noqa: E402
from tools import clear_miss_cache, run_tool  # noqa: E402
from schemas import request_from_dict  # noqa: E402


def _base_payload(**overrides):
    data = {
        "utterance": "rice and dal",
        "timezone": "America/Chicago",
        "dayKey": "2026-10-12",
        "preferenceContext": {
            "likes": ["high protein"],
            "dislikes": ["cilantro"],
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
        "conversation": {
            "summary": "",
            "recentTurns": [],
            "workingMemory": None,
        },
        "context": {"assistanceLevel": "fullAssist", "lastIntent": None},
    }
    data.update(overrides)
    return data


def test_log_meal_finds_seed_foods():
    clear_miss_cache()
    out = run_interpret(_base_payload(utterance="I had rice and dal"))
    assert out["intent"] in {"log_meal", "clarify"}
    ids = {c["foodId"] for c in out.get("candidates") or []}
    # USDA rice and/or overlay dal
    assert ids, out
    assert any(
        "rice" in (c.get("displayName") or "").lower()
        or c.get("foodId", "").startswith("seed_dal")
        or "dal" in (c.get("displayName") or "").lower()
        for c in out.get("candidates") or []
    )


def test_clarify_followup_uses_working_memory():
    clear_miss_cache()
    first = run_interpret(
        _base_payload(utterance="some rice")
    )
    assert first["intent"] == "clarify"
    assert first.get("clarifyingQuestion")
    follow = run_interpret(
        _base_payload(
            utterance="half",
            conversation={
                "summary": "awaiting portion on rice",
                "recentTurns": [
                    {"role": "user", "text": "some rice"},
                    {"role": "assistant", "text": first["assistantMessage"]},
                ],
                "workingMemory": {
                    "pendingIntent": "clarify",
                    "clarifyingQuestion": first["clarifyingQuestion"],
                    "candidates": first.get("candidates")
                    or [
                        {
                            "foodId": "usda_168878",
                            "displayName": "Rice, white, long-grain, regular, enriched, cooked",
                            "grams": None,
                        }
                    ],
                },
            },
        )
    )
    assert follow["intent"] == "log_meal"
    assert follow["candidates"]
    assert follow["candidates"][0].get("grams") == 75.0


def test_what_did_i_eat_uses_today_tool_context():
    clear_miss_cache()
    req = request_from_dict(
        _base_payload(
            utterance="what did I eat?",
            diaryContext={
                "today": [{"name": "Greek yogurt", "mealSlot": "Breakfast", "grams": 200}],
                "previousDays": [],
                "remaining": {
                    "calories": 1800,
                    "proteinG": 120,
                    "carbsG": 180,
                    "fatG": 55,
                },
                "remainingSource": "clientComputed",
            },
        )
    )
    today = run_tool("get_today_food_log", req)
    assert today["entries"][0]["name"] == "Greek yogurt"


def test_vegetarian_suggest_filters_poultry():
    clear_miss_cache()
    out = run_interpret(
        _base_payload(
            utterance="suggest something for dinner",
            preferenceContext={
                "likes": [],
                "dislikes": [],
                "allergies": [],
                "diets": ["vegetarian"],
            },
        )
    )
    assert out["intent"] in {"suggest_meal", "unknown"}
    for c in out.get("candidates") or []:
        assert "chicken" not in c["displayName"].lower()
        assert not c["foodId"].startswith("seed_chicken")


def test_long_term_memory_add_proposal():
    clear_miss_cache()
    out = run_interpret(
        _base_payload(utterance="remember I don't have a microwave at work")
    )
    assert out["intent"] == "update_memory"
    props = out.get("memoryProposals") or []
    assert props and props[0]["action"] == "add"
    assert "microwave" in (props[0].get("text") or "").lower()


def test_forget_memory_delete_proposal():
    clear_miss_cache()
    out = run_interpret(
        _base_payload(
            utterance="forget the microwave thing",
            longTermMemory=[
                {"id": "mem_1", "text": "No microwave at work"},
                {"id": "mem_2", "text": "Trains on Tuesdays"},
            ],
        )
    )
    assert out["intent"] == "update_memory"
    props = out.get("memoryProposals") or []
    assert any(p.get("action") == "delete" and p.get("id") == "mem_1" for p in props)


def test_long_thread_window_payload_still_runs():
    turns = []
    for i in range(20):
        turns.append({"role": "user", "text": f"note {i}"})
        turns.append({"role": "assistant", "text": f"ok {i}"})
    out = run_interpret(
        _base_payload(
            utterance="I had oats",
            conversation={
                "summary": "user logged many snacks · prior intents log_meal",
                "recentTurns": turns[-12:],
                "workingMemory": None,
            },
        )
    )
    assert out["intent"] in {"log_meal", "clarify"}
    assert "assistantMessage" in out


def test_no_trusted_macros_in_response():
    out = run_interpret(_base_payload(utterance="I had chicken breast 150g"))
    blob = str(out)
    for c in out.get("candidates") or []:
        assert "calories" not in c
        assert "proteinG" not in c
    assert "phase0_scaffold" not in blob


def test_search_food_seed_hit():
    clear_miss_cache()
    req = request_from_dict(_base_payload())
    result = run_tool("search_food", req, query="paneer")
    assert result["cache"] in {"hit", "usda"}
    assert any(r["foodId"] == "seed_paneer" for r in result["results"])
