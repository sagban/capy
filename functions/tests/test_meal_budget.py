"""Slot budget: stated, median of 3 days, weighted defaults, snacks."""

from schemas import request_from_dict

from agent.harness.meal_budget import fit_label, slot_budget


def _req(today=None, previous=None, remaining=None):
    return request_from_dict(
        {
            "utterance": "",
            "dayKey": "2026-10-13",
            "diaryContext": {
                "today": today or [],
                "previousDays": previous or [],
                "remaining": remaining
                or {"calories": 1600, "proteinG": 80, "carbsG": 150, "fatG": 40},
            },
        }
    )


def _item(slot, kcal, protein, day_grams=100):
    return {
        "name": "Lunch bowl",
        "mealSlot": slot,
        "grams": day_grams,
        "per100g": {
            "calories": kcal,
            "proteinG": protein,
            "carbsG": 10,
            "fatG": 5,
        },
    }


def test_stated_budget_capped_at_remaining():
    budget = slot_budget(_req(), "lunch", {"calories": 5000, "proteinG": 40})
    assert budget["calories"] == 1600
    assert budget["proteinG"] == 40


def test_median_of_three_lunch_days():
    previous = []
    for index, kcal in enumerate((400, 600, 800)):
        previous.append(
            {
                "dayKey": f"2026-10-0{index + 1}",
                "mealCount": 1,
                "entries": [_item("lunch", kcal, 30)],
            }
        )
    budget = slot_budget(_req(previous=previous), "lunch", None)
    # grams 100 so totals equal per100g. Median of 400, 600, 800 is 600.
    assert budget["calories"] == 600
    assert budget["proteinG"] == 30


def test_dinner_with_only_snacks_logged_uses_what_is_left():
    today = [_item("Snacks", 130, 3)]
    budget = slot_budget(
        _req(
            today=today,
            remaining={"calories": 825, "proteinG": 78, "carbsG": 72, "fatG": 28},
        ),
        "dinner",
        None,
    )
    assert budget["calories"] == 825
    assert budget["proteinG"] == 78


def test_breakfast_early_day_gets_modest_share_not_third_of_day():
    budget = slot_budget(
        _req(remaining={"calories": 2000, "proteinG": 140, "carbsG": 200, "fatG": 65}),
        "breakfast",
        None,
    )
    assert budget["calories"] == 2000 * 0.22
    assert budget["calories"] < 2000 / 3
    assert abs(budget["proteinG"] - 140 * 0.22) < 0.01


def test_lunch_after_breakfast_gets_moderate_share_not_half_of_remaining():
    today = [_item("breakfast", 400, 20)]
    budget = slot_budget(_req(today=today), "lunch", None)
    assert budget["calories"] == 1600 * 0.35
    assert budget["proteinG"] == 80 * 0.35
    assert budget["calories"] < 800


def test_snacks_get_small_allowance_not_main_meal_share():
    budget = slot_budget(_req(), "Snacks", None)
    assert budget["calories"] == 1600 * 0.12
    assert budget["calories"] <= 250
    assert budget["calories"] < 1600 * 0.22


def test_snack_allowance_caps_at_max():
    budget = slot_budget(
        _req(remaining={"calories": 3000, "proteinG": 200, "carbsG": 300, "fatG": 80}),
        "snack",
        None,
    )
    assert budget["calories"] == 250


def test_zero_remaining_is_zero_and_over():
    budget = slot_budget(
        _req(remaining={"calories": 0, "proteinG": 0, "carbsG": 0, "fatG": 0}),
        "breakfast",
        None,
    )
    assert budget["calories"] == 0
    assert fit_label(350, 20, budget) == "over"


def test_under_calorie_target_is_within():
    assert fit_label(350, 30, {"calories": 700, "proteinG": 20}) == "within"


def test_smaller_meal_is_within_even_with_low_protein():
    assert fit_label(350, 10, {"calories": 700, "proteinG": 40}) == "within"
