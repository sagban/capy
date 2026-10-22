from agent.tools.registry import TOOL_DECLARATIONS


def _by_name(name: str) -> dict:
    return next(d for d in TOOL_DECLARATIONS if d["name"] == name)


def test_log_meal_write_rejects_missing_per100g():
    from firebase_functions import https_fn

    from user_api import _validate_items

    try:
        _validate_items([{"name": "Egg", "grams": 50}])
    except https_fn.HttpsError as exc:
        assert exc.code == https_fn.FunctionsErrorCode.INVALID_ARGUMENT
        assert "per100g" in exc.message
        return
    raise AssertionError("a log item without per100g should be rejected")


def test_write_food_entry_is_one_entry():
    params = _by_name("write_food_entry")["parameters"]
    assert "items" not in params["properties"]
    assert "kind" in params.get("required", [])
    assert "name" in params.get("required", [])
    assert "grams" in params.get("required", [])
    assert "per100g" in params.get("required", [])


def test_gemini_schema_does_not_keep_json_schema_title_metadata():
    params = _by_name("search_catalog")["parameters"]
    assert "title" not in params
    assert "query" in params["properties"]


def test_delete_meal_requires_entry_id():
    params = _by_name("delete_food_entry")["parameters"]
    assert "entry_id" in params["properties"]
    assert "entry_id" in params.get("required", [])
    assert "day_key" in params.get("required", [])


def test_orchestrators_are_gone():
    names = {d["name"] for d in TOOL_DECLARATIONS}
    for gone in (
        "search_items",
        "stage_log",
        "compose_suggestions",
        "set_amount",
        "replace_item",
        "remove_item",
        "delete_entry",
        "repeat_prior_meal",
        "confirm_log",
    ):
        assert gone not in names
    for name in ("search_catalog", "search_usda", "search_library", "lookup_barcode", "portion_to_grams", "get_diary", "write_food_entry", "delete_food_entry"):
        assert name in names
        assert "When to use" in _by_name(name)["description"]


def test_search_library_does_not_ask_the_model_for_rows():
    params = _by_name("search_library")["parameters"]
    assert "items" not in params["properties"]
    assert "query" in params["properties"]
