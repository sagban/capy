from agent.harness.format import clarify_question, format_message
from agent.harness.messaging import looks_like_structured_dump, sanitize_assistant_message


def test_structured_dump_is_not_shown_to_user():
    dump = "{'foodId': 'est_abc', 'displayName': 'Quiche', 'per100g': {'calories': 280}}"
    assert looks_like_structured_dump(dump)
    text = format_message(
        draft=dump,
        outcome={
            "items": [
                {"displayName": "Quiche", "grams": 150},
                {"displayName": "Iced Latte", "grams": 473},
            ]
        },
    )
    assert "foodId" not in text
    assert "per100g" not in text
    assert "Ready to log Quiche and Iced Latte." == text


def test_sanitize_drops_structured_dump():
    assert sanitize_assistant_message("{'foodId': 'x', 'per100g': {}}") != "{'foodId': 'x', 'per100g': {}}"
    assert "foodId" not in sanitize_assistant_message("{'foodId': 'x', 'per100g': {}}")


def test_human_prose_is_not_followed_by_harness_line():
    text = format_message(
        draft="Staged a slice of quiche and an iced latte from First Cup — confirm when you're ready.",
        outcome={
            "items": [
                {"displayName": "Quiche", "grams": 150},
                {"displayName": "Iced Latte", "grams": 473},
            ]
        },
    )
    assert "Staged a slice of quiche" in text
    assert "Ready to log" not in text


def test_memory_note_without_model_text():
    text = format_message(
        draft="",
        outcome={"memory": [{"action": "add", "text": "vegetarian"}]},
    )
    assert "vegetarian" in text.lower()


def test_no_surviving_suggestion_still_has_a_sentence():
    text = format_message(
        draft="",
        outcome={"reason": "no suggestion survived", "dropped": ["opt: unresolved"]},
    )
    assert "couldn't source" in text.lower()


def test_venue_needs_citation_explains_menu_nutrition():
    text = format_message(
        draft="",
        outcome={
            "reason": "no suggestion survived",
            "dropped": ["Latte: unresolved (venue_needs_citation)"],
        },
    )
    assert "menu nutrition" in text.lower()


def test_empty_suggestion_draft_still_explains_the_options():
    text = format_message(
        draft="",
        outcome={
            "budget": {"calories": 825, "proteinG": 78},
            "day": {
                "eaten": ["egg whites", "coffee"],
                "remaining": {"calories": 1540, "proteinG": 84},
            },
            "options": [
                {
                    "title": "Tofu salad",
                    "fit": "within",
                    "totals": {"calories": 297, "proteinG": 24},
                    "items": ["200 g tofu"],
                },
                {
                    "title": "Greek yogurt bowl",
                    "fit": "within",
                    "totals": {"calories": 222, "proteinG": 26},
                },
            ],
        },
    )
    assert "egg whites" in text
    assert "Tofu salad" in text
    assert "Greek yogurt bowl" in text
    assert "297" in text
    assert "825" in text
    assert "on track" in text.lower()
    assert "200 g tofu" not in text
    assert "\n\n" in text


def test_portion_question_does_not_call_a_tablespoon_the_food():
    text = clarify_question(
        {
            "kind": "clarify_portion",
            "reason": "need_amount",
            "food": "whole eggs",
            "quantity": 2,
            "unit": "whole eggs",
            "options": ["3 Tbsp (47 g)"],
        }
    )
    assert "Which one" not in text
    assert "3 Tbsp" not in text
    assert "2 whole eggs" in text
    assert "grams" in text
