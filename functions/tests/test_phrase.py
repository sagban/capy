from agent.harness.format import clarify_question, format_message


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


def test_empty_suggestion_draft_still_explains_the_options():
    text = format_message(
        draft="",
        outcome={
            "budget": {"calories": 825, "proteinG": 78},
            "options": [
                {
                    "title": "Tofu salad",
                    "fit": "within",
                    "totals": {"calories": 297, "proteinG": 24},
                    "items": ["200 g tofu"],
                }
            ],
        },
    )
    assert "Tofu salad" in text
    assert "297" in text
    assert "825" in text
    assert "200 g tofu" not in text


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
