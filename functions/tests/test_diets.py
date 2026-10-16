from agent.harness.diets import diets_from_text, item_breaks_diet


def test_utterance_vegetarian():
    assert "vegetarian" in diets_from_text("I am vegetarian")
    assert item_breaks_diet("Chicken breast", "poultry", ["vegetarian"])
    assert item_breaks_diet("Salmon", "fish", ["vegetarian"])
    assert not item_breaks_diet("Tofu", "soy", ["vegetarian"])
    assert not item_breaks_diet("Egg", "egg", ["vegetarian"])
    assert item_breaks_diet("Egg", "egg", ["vegan"])
