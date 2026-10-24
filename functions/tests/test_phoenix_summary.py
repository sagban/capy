"""Phoenix tool spans record a short result, not the full payload."""

from phoenix_tracing import tool_result_summary


def test_lookup_summary_keeps_names_and_drops_macros():
    summary = tool_result_summary(
        "search_catalog",
        {
            "source": "catalog",
            "hits": [
                {"displayName": "Egg, whole", "foodId": "egg", "per100g": {"calories": 143}},
                {"displayName": "Egg white", "foodId": "white"},
            ],
        },
    )
    assert summary == {
        "tool": "search_catalog",
        "source": "catalog",
        "hitCount": 2,
        "hits": ["Egg, whole", "Egg white"],
    }


def test_portion_summary_is_grams():
    assert tool_result_summary("portion_to_grams", {"grams": 50, "label": "1 large"}) == {
        "tool": "portion_to_grams",
        "grams": 50,
        "label": "1 large",
    }
    assert tool_result_summary("portion_to_grams", {"unmapped": True}) == {
        "tool": "portion_to_grams",
        "unmapped": True,
    }


def test_staged_write_names_the_item():
    summary = tool_result_summary(
        "write_food_entry",
        {
            "staged": True,
            "pendingType": "confirm_log",
            "items": [{"displayName": "Egg, whole", "grams": 50, "per100g": {"calories": 143}}],
        },
    )
    assert summary == {
        "tool": "write_food_entry",
        "staged": True,
        "pendingType": "confirm_log",
        "items": ["Egg, whole 50 g"],
    }


def test_error_summary_keeps_the_message():
    assert tool_result_summary("search_catalog", {"error": "bad_args", "message": "query is empty"}) == {
        "tool": "search_catalog",
        "error": "bad_args",
        "message": "query is empty",
    }


def test_diary_summary_names_entries():
    summary = tool_result_summary(
        "get_diary",
        {
            "dayKey": "2026-10-23",
            "entries": [{"name": "Oatmeal", "grams": 240, "per100g": {"calories": 70}}],
            "remaining": {"calories": 400},
        },
    )
    assert summary == {
        "tool": "get_diary",
        "dayKey": "2026-10-23",
        "entryCount": 1,
        "entries": ["Oatmeal 240 g"],
    }
