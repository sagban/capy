"""Graph paths with the shared tools. The model turn is scripted."""

from __future__ import annotations

from agent.graph import reset_graph, run_interpret
from agent.harness.mock_turn import push_mock_turns
from agent.harness.outcomes import normalize_outcome
from agent.tools.lookups import set_lookup_overrides
from schemas import MacroTotals, request_from_dict

PER = {"calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11}
EGG = {
    "foodId": "seed_egg",
    "displayName": "Egg",
    "source": "seed",
    "per100g": PER,
    "family": "egg",
    "measures": [{"id": "m0", "label": "1 large", "grams": 50}],
}
MEASURES = EGG["measures"]


def setup_function(_fn):
    reset_graph()


def _payload(utterance="", **over):
    base = {
        "utterance": utterance,
        "timezone": "UTC",
        "dayKey": "2026-10-13",
        "preferenceContext": {"likes": [], "dislikes": [], "allergies": [], "diets": []},
        "diaryContext": {
            "today": [],
            "previousDays": [],
            "remaining": {"calories": 1600, "proteinG": 80, "carbsG": 150, "fatG": 40},
        },
        "longTermMemory": [],
        "conversation": {"summary": "", "recentTurns": [], "workingMemory": None},
        "context": {"assistanceLevel": "fullAssist", "lastIntent": None},
    }
    base.update(over)
    return base


def _catalog(query, limit=10):
    del limit
    if "chicken" in (query or "").lower():
        row = {
            "foodId": "usda_1",
            "displayName": "Chicken A",
            "source": "usda",
            "per100g": {"calories": 165, "proteinG": 31, "carbsG": 0, "fatG": 3.6},
            "family": "poultry",
            "measures": [{"id": "oz", "label": "1 ounce", "grams": 28}],
        }
        other = {**row, "foodId": "usda_2", "displayName": "Chicken B"}
        return {"source": "catalog", "hits": [row, other]}
    if "oil" in (query or "").lower():
        return {
            "source": "catalog",
            "hits": [
                {
                    "foodId": "oil_1",
                    "displayName": "Olive oil",
                    "source": "usda",
                    "per100g": {"calories": 884, "proteinG": 0, "carbsG": 0, "fatG": 100},
                    "family": "oil",
                    "measures": [{"id": "tbsp", "label": "1 tablespoon", "grams": 13.5}],
                }
            ],
        }
    return {"source": "catalog", "hits": [EGG]}


def _install():
    set_lookup_overrides(catalog=_catalog)


def _egg_item(grams: float) -> dict:
    return {
        "name": "Egg",
        "grams": grams,
        "foodId": "seed_egg",
        "source": "seed",
        "per100g": PER,
        "ingredientFamily": "egg",
    }


def _portion(quantity: float, unit: str = "large") -> dict:
    return {
        "name": "portion_to_grams",
        "arguments": {"quantity": quantity, "unit": unit, "measures": MEASURES},
    }


def _log(item: dict, **extra) -> dict:
    arguments = {"day_key": "2026-10-13", "meal_slot": "breakfast", "kind": "food"}
    arguments.update(item)
    arguments.update(extra)
    return {"name": "write_food_entry", "arguments": arguments}


def test_log_multi_item_confirm():
    _install()
    push_mock_turns(
        [
            {"kind": "tool_calls", "calls": [{"name": "search_catalog", "arguments": {"query": "egg"}}]},
            {"kind": "tool_calls", "calls": [_portion(2), _portion(1)]},
            {"kind": "tool_calls", "text": "Ready to log the egg.", "calls": [_log(_egg_item(100))]},
        ]
    )
    out = run_interpret(_payload("two eggs and an egg"))
    normalize_outcome(out)
    assert out["pendingAction"]["type"] == "confirm_log"
    assert len(out["pendingAction"]["payload"]["resolvedItems"]) == 1
    assert out["workingMemory"]["draftLog"]
    assert "Ready to log the egg." in out["assistantMessage"]


def test_several_hits_do_not_pick():
    _install()
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "text": "Which chicken — A or B?",
                "calls": [{"name": "search_catalog", "arguments": {"query": "chicken"}}],
            },
            {"kind": "text", "text": "Which chicken — A or B?"},
        ]
    )
    out = run_interpret(_payload("chicken sandwich"))
    assert out["pendingAction"] is None
    assert "Which chicken" in out["assistantMessage"]


def test_change_amount_stages_correction():
    _install()
    diary = {
        "today": [
            {
                "name": "Egg",
                "mealSlot": "breakfast",
                "grams": 50,
                "entryId": "meal-1",
                "itemIndex": 0,
                "foodId": "seed_egg",
                "source": "seed",
                "per100g": PER,
                "ingredientFamily": "egg",
            }
        ],
        "previousDays": [],
        "remaining": {"calories": 1600, "proteinG": 80, "carbsG": 150, "fatG": 40},
    }
    push_mock_turns(
        [
            {"kind": "tool_calls", "calls": [_portion(3)]},
            {
                "kind": "tool_calls",
                "calls": [_log(_egg_item(150), entry_id="meal-1")],
            },
        ]
    )
    out = run_interpret(_payload("make it 3", diaryContext=diary))
    assert out["pendingAction"]["type"] == "confirm_correction"
    assert out["pendingAction"]["payload"]["resolvedItems"][0]["grams"] == 150
    assert out["pendingAction"]["payload"]["entryId"] == "meal-1"


def test_suggest_from_lookups():
    _install()
    push_mock_turns(
        [
            {"kind": "tool_calls", "calls": [{"name": "search_catalog", "arguments": {"query": "egg"}}]},
            {"kind": "tool_calls", "calls": [_portion(2)]},
            {"kind": "text", "text": "Eggs fit what's left."},
        ]
    )
    suggested = run_interpret(_payload("suggest lunch"))
    normalize_outcome(suggested)
    assert suggested["pendingAction"] is None
    assert suggested["intent"] == "suggest_meal"
    assert suggested["suggestionOptions"][0]["fit"] in {"within", "over"}
    assert suggested["suggestionOptions"][0]["totals"]["calories"] > 0
    push_mock_turns(
        [
            {"kind": "tool_calls", "calls": [_log(_egg_item(50))]},
        ]
    )
    logged = run_interpret(
        _payload(
            "log that egg",
            conversation={"summary": "", "recentTurns": [], "workingMemory": suggested["workingMemory"]},
        )
    )
    assert logged["pendingAction"]["type"] == "confirm_log"
    assert logged["pendingAction"]["payload"]["resolvedItems"][0]["grams"] == 50


def test_repeat_and_correct_by_entry_id():
    diary = {
        "today": [
            {
                "name": "Egg",
                "mealSlot": "breakfast",
                "grams": 100,
                "entryId": "meal-1",
                "itemIndex": 0,
                "foodId": "seed_egg",
                "source": "diary",
                "per100g": PER,
                "ingredientFamily": "egg",
            }
        ],
        "previousDays": [],
        "remaining": {"calories": 1600, "proteinG": 80, "carbsG": 150, "fatG": 40},
    }
    item = {**_egg_item(100), "source": "diary"}
    push_mock_turns([{"kind": "tool_calls", "calls": [_log(item)]}])
    repeated = run_interpret(_payload("same breakfast", diaryContext=diary))
    assert repeated["pendingAction"]["type"] == "confirm_log"
    assert repeated["pendingAction"]["payload"]["resolvedItems"][0]["source"] == "diary"
    assert repeated["pendingAction"]["payload"]["resolvedItems"][0]["grams"] == 100

    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "portion_to_grams",
                        "arguments": {"quantity": 80, "unit": "g", "measures": []},
                    }
                ],
            },
            {"kind": "tool_calls", "calls": [_log({**_egg_item(80), "source": "diary"}, entry_id="meal-1")]},
        ]
    )
    corrected = run_interpret(_payload("make it 80 g", diaryContext=diary))
    assert corrected["pendingAction"]["type"] == "confirm_correction"
    assert corrected["pendingAction"]["payload"]["entryId"] == "meal-1"
    assert corrected["pendingAction"]["payload"]["resolvedItems"][0]["grams"] == 80


def test_delete_meal_stages_confirm_delete():
    diary = {
        "today": [
            {
                "name": "Egg",
                "mealSlot": "Lunch",
                "grams": 100,
                "entryId": "meal-friday",
                "itemIndex": 0,
                "foodId": "seed_egg",
                "source": "catalog",
                "per100g": PER,
                "ingredientFamily": "egg",
            }
        ],
        "previousDays": [],
        "remaining": {"calories": 1600, "proteinG": 80, "carbsG": 150, "fatG": 40},
    }
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [
                    {"name": "delete_food_entry", "arguments": {"day_key": "2026-10-13", "entry_id": "meal-friday"}}
                ],
            }
        ]
    )
    out = run_interpret(_payload("delete friday lunch", diaryContext=diary))
    normalize_outcome(out)
    assert out["pendingAction"]["type"] == "confirm_delete"
    assert out["pendingAction"]["payload"]["entryId"] == "meal-friday"
    assert out["pendingAction"]["payload"]["dayKey"] == "2026-10-13"
    assert "Egg" in (out["pendingAction"]["payload"].get("reason") or "")


def test_diet_conflict_stays_on_the_hit():
    _install()
    from agent.harness.execute import run_calls

    req = request_from_dict(_payload("I am vegetarian, what should I eat"))
    trace, _out = run_calls(
        req,
        [
            {"name": "search_catalog", "arguments": {"query": "chicken"}},
            {"name": "search_catalog", "arguments": {"query": "egg"}},
        ],
        uid="test",
    )
    chicken = trace[0]["result"]["hits"]
    assert chicken
    assert all(hit.get("conflict") == "diet" for hit in chicken)
    egg = trace[1]["result"]["hits"][0]
    assert egg["displayName"] == "Egg"
    assert "conflict" not in egg


def test_ambiguous_search_uses_the_hit_the_caller_portioned():
    _install()
    chicken_measures = [{"id": "oz", "label": "1 ounce", "grams": 28}]
    push_mock_turns(
        [
            {"kind": "tool_calls", "calls": [{"name": "search_catalog", "arguments": {"query": "chicken"}}]},
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "portion_to_grams",
                        "arguments": {"quantity": 5, "unit": "oz", "measures": chicken_measures},
                    }
                ],
            },
            {"kind": "text", "text": "Chicken A is one way to use the slot."},
        ]
    )
    out = run_interpret(_payload("suggest lunch"))
    normalize_outcome(out)
    assert "Chicken" in out["suggestionOptions"][0]["items"][0]["displayName"]
    assert out["assistantMessage"]


def test_dinner_tool_keeps_the_model_sentence():
    _install()
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "text": "Eggs are a simple dinner with what you have left.",
                "calls": [{"name": "search_catalog", "arguments": {"query": "egg"}}],
            },
            {"kind": "tool_calls", "calls": [_portion(2)]},
            {"kind": "text", "text": ""},
        ]
    )
    out = run_interpret(_payload("What should I eat for dinner."))
    normalize_outcome(out)
    assert out["suggestionOptions"]
    assert out["pendingAction"] is None
    assert "Eggs are a simple dinner" in out["assistantMessage"]


def test_memory_add_and_remove_with_chat():
    push_mock_turns(
        [
            {"kind": "text", "text": ""},
            {"kind": "text", "text": "What did you have."},
        ]
    )
    added = run_interpret(_payload("remember no cilantro"))
    assert added["memoryProposals"][0]["action"] == "add"
    assert added["memoryProposals"][0]["text"] == "no cilantro"
    assert "cilantro" in added["assistantMessage"].lower()
    chat = run_interpret(_payload("what did I have"))
    assert chat["pendingAction"] is None
    assert chat["intent"] == "unknown"


def test_log_does_not_also_build_suggestion_cards():
    _install()
    push_mock_turns(
        [
            {"kind": "tool_calls", "calls": [{"name": "search_catalog", "arguments": {"query": "egg"}}]},
            {"kind": "tool_calls", "calls": [_portion(1), _log(_egg_item(50))]},
        ]
    )
    out = run_interpret(_payload("log an egg and suggest lunch"))
    normalize_outcome(out)
    assert out["pendingAction"]["type"] == "confirm_log"
    assert out["suggestionOptions"] == []


def test_oil_portion_is_not_clamped():
    _install()
    push_mock_turns(
        [
            {"kind": "tool_calls", "calls": [{"name": "search_catalog", "arguments": {"query": "olive oil"}}]},
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "portion_to_grams",
                        "arguments": {"quantity": 200, "unit": "ml", "measures": []},
                    }
                ],
            },
            {"kind": "text", "text": "Olive oil is 200 ml."},
        ]
    )
    out = run_interpret(_payload("what should I eat"))
    normalize_outcome(out)
    oil = out["suggestionOptions"][0]["items"][0]
    assert oil["grams"] == 200


def test_unmapped_unit_does_not_become_a_card():
    _install()
    push_mock_turns(
        [
            {"kind": "tool_calls", "calls": [{"name": "search_catalog", "arguments": {"query": "egg"}}]},
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "portion_to_grams",
                        "arguments": {"quantity": 1, "unit": "handful", "measures": []},
                    }
                ],
            },
            {"kind": "text", "text": "I don't know that unit."},
        ]
    )
    out = run_interpret(_payload("a handful of egg"))
    assert out["suggestionOptions"] == []
    assert out["pendingAction"] is None


def test_infra_failure_is_agent_unavailable():
    push_mock_turns([{"kind": "error", "message": "unavailable"}, {"kind": "error", "message": "unavailable"}])
    out = run_interpret(_payload("log an egg"))
    assert out["warnings"][0] == "agent_unavailable"
    assert out["assistantMessage"] == ""
    assert out["pendingAction"] is None


def test_bad_args_do_not_run_the_tool():
    _install()
    push_mock_turns(
        [
            {"kind": "tool_calls", "text": "Which egg?", "calls": [{"name": "search_catalog", "arguments": {"query": ""}}]},
            {"kind": "tool_calls", "text": "Which egg?", "calls": [{"name": "search_catalog", "arguments": {"query": ""}}]},
        ]
    )
    out = run_interpret(_payload("egg"))
    assert out.get("pendingAction") is None
    assert out["assistantMessage"] == "Which egg?"


def test_unknown_entry_does_not_stage():
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [{"name": "delete_food_entry", "arguments": {"day_key": "2026-10-13", "entry_id": "missing"}}],
            },
            {"kind": "text", "text": "I can't find that meal."},
        ]
    )
    out = run_interpret(_payload("same breakfast"))
    assert out["pendingAction"] is None
    assert out["intent"] == "unknown"


def test_executor_outputs_normalize():
    _install()
    from agent.harness.execute import run_calls

    req = request_from_dict(_payload("egg"))
    _trace, out = run_calls(
        req,
        [
            {"name": "search_catalog", "arguments": {"query": "egg"}},
            _portion(1),
            _log(_egg_item(50)),
        ],
        uid="test",
    )
    out.pop("phraseFacts", None)
    out["assistantMessage"] = ""
    normalize_outcome(out)
    assert MacroTotals.model_validate(out["pendingAction"]["payload"]["resolvedItems"][0]["per100g"])


def test_confirmed_log_writes_through_log_meal(monkeypatch):
    seen: dict = {}

    def fake(uid, raw):
        seen["uid"] = uid
        seen["raw"] = raw
        return {"dayKey": raw["dayKey"], "entryId": "e1"}

    monkeypatch.setattr("agent.tools.diary_io.log_meal_for_uid", fake)
    push_mock_turns([{"kind": "tool_calls", "text": "Logged the egg.", "calls": [_log(_egg_item(50))]}])
    pending = {
        "pendingIntent": "confirm_log",
        "pendingAction": {
            "type": "confirm_log",
            "prompt": "",
            "payload": {
                "resolvedItems": [
                    {
                        "foodId": "seed_egg",
                        "displayName": "Egg",
                        "grams": 50,
                        "per100g": PER,
                        "source": "seed",
                    }
                ]
            },
        },
    }
    out = run_interpret(
        _payload(
            "yes",
            conversation={"summary": "", "recentTurns": [], "workingMemory": pending},
        )
    )
    assert seen["uid"] == "test"
    assert seen["raw"]["mealSlot"] == "breakfast"
    assert seen["raw"]["dayKey"] == "2026-10-13"
    assert seen["raw"]["items"][0]["name"] == "Egg"
    assert out["pendingAction"] is None
    assert out["intent"] == "log_meal"
    assert "Logged the egg." in out["assistantMessage"]


def test_confirm_does_not_write_a_different_food(monkeypatch):
    def fake(uid, raw):
        del uid, raw
        raise AssertionError("write should wait for the same food")

    monkeypatch.setattr("agent.tools.diary_io.log_meal_for_uid", fake)
    other = {**PER, "calories": 400}
    push_mock_turns(
        [{"kind": "tool_calls", "text": "That is a different egg.", "calls": [_log({**_egg_item(50), "per100g": other})]}]
    )
    pending = {
        "pendingIntent": "confirm_log",
        "pendingAction": {
            "type": "confirm_log",
            "prompt": "",
            "payload": {
                "resolvedItems": [
                    {
                        "foodId": "seed_egg",
                        "displayName": "Egg",
                        "grams": 50,
                        "per100g": PER,
                        "source": "seed",
                    }
                ]
            },
        },
    }
    out = run_interpret(
        _payload(
            "yes",
            conversation={"summary": "", "recentTurns": [], "workingMemory": pending},
        )
    )
    assert out["pendingAction"]["type"] == "confirm_log"
    assert out["pendingAction"]["payload"]["resolvedItems"][0]["per100g"]["calories"] == 400
