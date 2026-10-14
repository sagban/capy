"""Phrase validator drops ungrounded numbers and food names."""

from harness.phrase import validate_message


def test_ungrounded_number_stripped():
    text = validate_message(
        "Egg is 50 g. That is about 900 cal.",
        {"items": [{"displayName": "Egg", "grams": 50}]},
    )
    assert "50" in text
    assert "900" not in text


def test_unknown_food_name_stripped():
    text = validate_message(
        "Egg is logged. Also have pizza.",
        {"items": [{"displayName": "Egg"}]},
    )
    assert "egg" in text.lower()
    assert "pizza" not in text.lower()


def test_suggestion_reply_keeps_normal_words():
    text = validate_message(
        "Lentil soup is a light dinner at 305 cal, within the 825 cal you have left.",
        {
            "budget": {"calories": 825, "proteinG": 78},
            "options": [
                {"title": "Lentil soup", "fit": "within", "totals": {"calories": 305, "proteinG": 18}}
            ],
        },
    )
    assert "light" in text
    assert "305" in text


def test_empty_suggestion_draft_still_explains_the_options():
    from harness.phrase import phrase_message

    text = phrase_message(
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
        context_pack="",
        user_text="What should I eat for dinner.",
        generate=None,
    )
    assert "Tofu salad" in text
    assert "297" in text
    assert "825" in text


def test_log_status_with_no_food_is_dropped():
    text = validate_message(
        "Nothing was logged.",
        {"today": [{"name": "Egg"}]},
    )
    assert text == ""


def test_empty_when_nothing_survives():
    text = validate_message("Have some pizza.", {"items": [{"displayName": "Egg"}]})
    assert text == ""
