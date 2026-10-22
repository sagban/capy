from agent.tools.search.recipes_store import (
    build_recipe_document,
    normalize_ingredients,
    recipe_from_composite_seed_raw,
)


def test_normalize_ingredients():
    raw = [{"foodId": "seed_dal_cooked", "grams": 200}, {"foodId": "", "grams": 1}]
    assert normalize_ingredients(raw) == [{"foodId": "seed_dal_cooked", "grams": 200.0}]


def test_recipe_from_composite():
    doc = recipe_from_composite_seed_raw(
        "seed_dal_tadka_bowl",
        {
            "id": "seed_dal_tadka_bowl",
            "name": "Dal tadka bowl",
            "components": [
                {"foodId": "seed_dal_cooked", "grams": 200},
                {"foodId": "usda_171413", "grams": 5},
            ],
        },
        catalog_version=2,
    )
    assert doc is not None
    assert doc["kind"] == "composite"
    assert len(doc["ingredients"]) == 2
    assert doc["recipeId"] == "seed_dal_tadka_bowl"


def test_build_recipe_user_kind():
    doc = build_recipe_document(
        recipe_id="user_abc",
        name="My bowl",
        ingredients=[{"foodId": "usda_1", "grams": 100}],
        kind="recipe",
        notes="weeknight",
    )
    assert doc["kind"] == "recipe"
    assert doc["notes"] == "weeknight"
