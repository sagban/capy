from agent.harness.tools.registry import TOOL_DECLARATIONS


def _by_name(name: str) -> dict:
    return next(d for d in TOOL_DECLARATIONS if d["name"] == name)


def test_compose_suggestions_keeps_draft_title_property():
    params = _by_name("compose_suggestions")["parameters"]
    meal = params["properties"]["drafts"]["items"]
    assert "title" in meal["properties"]
    assert "title" in meal.get("required", [])
    assert meal["properties"]["title"]["type"] == "string"


def test_gemini_schema_does_not_keep_json_schema_title_metadata():
    params = _by_name("new_entry")["parameters"]
    assert "title" not in params
    items = params["properties"]["items"]
    assert "title" not in items


def test_delete_entry_requires_entry_id():
    params = _by_name("delete_entry")["parameters"]
    assert "entryId" in params["properties"]
    assert "entryId" in params.get("required", [])
    assert "dayKey" in params["properties"]


def test_edit_entry_requires_entry_and_index():
    params = _by_name("edit_entry")["parameters"]
    assert "entryId" in params.get("required", [])
    assert "itemIndex" in params.get("required", [])
    assert "op" in params.get("required", [])
