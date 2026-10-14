"""Per-job graph paths. The model turn is scripted; resolve search is injected."""

from __future__ import annotations

from graph import reset_graph, run_interpret
from harness.deps import set_overrides
from harness.mock_turn import push_mock_turns
from harness.outcomes import normalize_outcome
from schemas import MacroTotals, request_from_dict


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


def _egg_search(query):
    if "chicken" in query:
        row = {
            "foodId": "usda_1",
            "displayName": "Chicken A",
            "source": "usda",
            "per100g": {"calories": 165, "proteinG": 31, "carbsG": 0, "fatG": 3.6},
            "family": "poultry",
            "measures": [],
        }
        other = {**row, "foodId": "usda_2", "displayName": "Chicken B"}
        return {"results": [], "candidatesForClarify": [row, other], "confidence": "medium"}
    return {
        "results": [
            {
                "foodId": "seed_egg",
                "displayName": "Egg",
                "source": "seed",
                "per100g": {"calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11},
                "family": "egg",
                "measures": [{"id": "m0", "label": "1 large", "grams": 50}],
            }
        ],
        "candidatesForClarify": [],
        "confidence": "high",
    }


def _install_search():
    set_overrides(search=_egg_search, web=lambda _q: None, fetch_measures=lambda _fid: [])


def test_log_multi_item_confirm():
    _install_search()
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "resolve_meal",
                        "arguments": {
                            "items": [
                                {"foodQuery": "egg", "quantity": 2, "unit": "large"},
                                {"foodQuery": "egg", "quantity": 1, "unit": "large"},
                            ]
                        },
                    }
                ],
            }
        ]
    )
    out = run_interpret(_payload("two eggs and an egg"))
    normalize_outcome(out)
    assert out["pendingAction"]["type"] == "confirm_log"
    assert len(out["pendingAction"]["payload"]["resolvedItems"]) == 2
    assert out["workingMemory"]["draftLog"]


def test_chip_resume_and_typed_path_keep_queue():
    _install_search()
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "resolve_meal",
                        "arguments": {"items": [{"foodQuery": "chicken sandwich"}, {"foodQuery": "egg", "quantity": 1, "unit": "large"}]},
                    }
                ],
            }
        ]
    )
    first = run_interpret(_payload("chicken sandwich and an egg"))
    assert first["pendingAction"]["type"] == "clarify_food"
    queue = first["workingMemory"]["resolveQueue"]
    assert queue["remaining"][0]["foodQuery"] == "egg"
    option_id = first["pendingAction"]["payload"]["clarifyOptions"][0]["id"]
    # Chip sends an action. No model turn.
    resumed = run_interpret(
        _payload(
            "",
            action={"type": "pick_candidate", "id": option_id},
            conversation={"summary": "", "recentTurns": [], "workingMemory": first["workingMemory"]},
        )
    )
    # Picked food has no household measure and the draft had no amount → grams field.
    assert resumed["pendingAction"]["type"] == "clarify_portion"
    assert resumed["pendingAction"]["payload"]["freeTextGrams"] is True


def test_edit_draft_changes_open_log():
    _install_search()
    memory = {
        "draftLog": [
            {
                "foodId": "seed_egg",
                "displayName": "Egg",
                "grams": 50,
                "per100g": {"calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11},
                "source": "catalog",
                "measures": [{"id": "m0", "label": "1 large", "grams": 50}],
            }
        ]
    }
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "edit_draft",
                        "arguments": {"ops": [{"op": "set_amount", "index": 0, "quantity": 3, "unit": "large"}]},
                    }
                ],
            }
        ]
    )
    out = run_interpret(
        _payload(
            "make it 3",
            conversation={"summary": "", "recentTurns": [], "workingMemory": memory},
        )
    )
    assert out["pendingAction"]["type"] == "confirm_log"
    assert out["pendingAction"]["payload"]["resolvedItems"][0]["grams"] == 150


def test_suggest_then_log_by_action_and_by_text():
    _install_search()
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "compose_suggestions",
                        "arguments": {
                            "mealSlot": "lunch",
                            "drafts": [
                                {"title": "Eggs", "items": [{"foodQuery": "egg", "quantity": 2, "unit": "large"}]}
                            ],
                        },
                    }
                ],
            }
        ]
    )
    suggested = run_interpret(_payload("suggest lunch"))
    normalize_outcome(suggested)
    assert suggested["pendingAction"] is None
    assert suggested["suggestionOptions"][0]["fit"] in {"within", "over"}
    assert suggested["suggestionOptions"][0]["totals"]["calories"] > 0
    option_id = suggested["suggestionOptions"][0]["id"]
    by_action = run_interpret(
        _payload(
            "",
            action={"type": "pick_option", "id": option_id},
            conversation={"summary": "", "recentTurns": [], "workingMemory": suggested["workingMemory"]},
        )
    )
    assert by_action["pendingAction"]["type"] == "confirm_log"
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "log_from_suggestion",
                        "arguments": {"optionId": option_id, "ops": [{"op": "set_amount", "index": 0, "quantity": 1, "unit": "large"}]},
                    }
                ],
            }
        ]
    )
    by_text = run_interpret(
        _payload(
            "log that with one egg",
            conversation={"summary": "", "recentTurns": [], "workingMemory": suggested["workingMemory"]},
        )
    )
    assert by_text["pendingAction"]["type"] == "confirm_log"
    assert by_text["pendingAction"]["payload"]["resolvedItems"][0]["grams"] == 50


def test_repeat_and_correct_by_entry_id():
    per = {"calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11}
    diary = {
        "today": [
            {
                "name": "Egg",
                "mealSlot": "breakfast",
                "grams": 100,
                "entryId": "meal-1",
                "itemIndex": 0,
                "foodId": "seed_egg",
                "source": "catalog",
                "per100g": per,
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
                "calls": [{"name": "repeat_prior_meal", "arguments": {"entryIds": ["meal-1"]}}],
            }
        ]
    )
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
                        "name": "correct_entry",
                        "arguments": {
                            "entryId": "meal-1",
                            "itemIndex": 0,
                            "op": "set_amount",
                            "quantity": 80,
                            "unit": "g",
                        },
                    }
                ],
            }
        ]
    )
    corrected = run_interpret(_payload("make it 80 g", diaryContext=diary))
    assert corrected["pendingAction"]["type"] == "confirm_correction"
    assert corrected["pendingAction"]["payload"]["entryId"] == "meal-1"
    assert corrected["pendingAction"]["payload"]["resolvedItems"][0]["grams"] == 80


def test_dinner_tool_keeps_the_model_sentence():
    _install_search()
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "text": "Eggs are a simple dinner with what you have left.",
                "calls": [
                    {
                        "name": "compose_suggestions",
                        "arguments": {
                            "mealSlot": "dinner",
                            "drafts": [
                                {"title": "Eggs", "items": [{"foodQuery": "egg", "quantity": 2, "unit": "large"}]}
                            ],
                        },
                    }
                ],
            }
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
            {
                "kind": "tool_calls",
                "calls": [{"name": "save_memory", "arguments": {"op": "add", "text": "no cilantro"}}],
            },
            {"kind": "text", "text": "What did you have."},
        ]
    )
    added = run_interpret(_payload("remember no cilantro"))
    assert added["memoryProposals"][0]["action"] == "add"
    assert added["memoryProposals"][0]["text"] == "no cilantro"
    chat = run_interpret(_payload("what did I have"))
    assert chat["pendingAction"] is None
    assert chat["intent"] == "unknown"


def test_combined_log_and_suggest():
    _install_search()
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [
                    {
                        "name": "resolve_meal",
                        "arguments": {"items": [{"foodQuery": "egg", "quantity": 1, "unit": "large"}]},
                    },
                    {
                        "name": "compose_suggestions",
                        "arguments": {
                            "mealSlot": "lunch",
                            "drafts": [
                                {"title": "Eggs", "items": [{"foodQuery": "egg", "quantity": 2, "unit": "large"}]}
                            ],
                        },
                    },
                ],
            }
        ]
    )
    out = run_interpret(_payload("log an egg and suggest lunch"))
    normalize_outcome(out)
    assert out["pendingAction"]["type"] == "confirm_log"
    assert out["suggestionOptions"]


def test_infra_failure_is_agent_unavailable():
    push_mock_turns([{"kind": "error", "message": "unavailable"}, {"kind": "error", "message": "unavailable"}])
    out = run_interpret(_payload("log an egg"))
    assert out["warnings"][0] == "agent_unavailable"
    assert out["assistantMessage"] == ""
    assert out["pendingAction"] is None


def test_bad_args_do_not_search_the_question_as_food():
    _install_search()
    push_mock_turns(
        [
            {"kind": "tool_calls", "text": "Which egg?", "calls": [{"name": "resolve_meal", "arguments": {"items": []}}]},
            {"kind": "tool_calls", "text": "Which egg?", "calls": [{"name": "resolve_meal", "arguments": {"items": []}}]},
        ]
    )
    out = run_interpret(_payload("egg"))
    assert out.get("pendingAction") is None
    assert out["assistantMessage"] == "Which egg?"


def test_repeat_miss_is_chat():
    push_mock_turns(
        [
            {
                "kind": "tool_calls",
                "calls": [{"name": "repeat_prior_meal", "arguments": {"entryIds": ["missing"]}}],
            }
        ]
    )
    out = run_interpret(_payload("same breakfast"))
    assert out["pendingAction"] is None
    assert out["intent"] == "unknown"


def test_executor_outputs_normalize():
    _install_search()
    from harness.execute import run_calls

    req = request_from_dict(_payload("egg"))
    out = run_calls(
        req,
        [{"name": "resolve_meal", "arguments": {"items": [{"foodQuery": "egg", "quantity": 1, "unit": "large"}]}}],
    )
    out.pop("phraseFacts", None)
    out["assistantMessage"] = ""
    normalize_outcome(out)
    assert MacroTotals.model_validate(out["pendingAction"]["payload"]["resolvedItems"][0]["per100g"])
