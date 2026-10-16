"""Portion grams: Swift unit parity, household measures, free-text when none exist."""

from schemas import HouseholdMeasure

from agent.harness.portions import SWIFT_PARITY_GRAMS, resolve_portion, suggestion_portion


def test_unit_factors_match_units_swift():
    # PortionUnit.gramsPerUnit in capy/Core/Units.swift
    assert SWIFT_PARITY_GRAMS["gram"] == 1
    assert SWIFT_PARITY_GRAMS["milliliter"] == 1
    assert SWIFT_PARITY_GRAMS["ounce"] == 28.349523125
    assert SWIFT_PARITY_GRAMS["teaspoon"] == 4.92892
    assert SWIFT_PARITY_GRAMS["tablespoon"] == 14.7868
    assert SWIFT_PARITY_GRAMS["cup"] == 236.588


def test_explicit_grams_and_ounces():
    grams = resolve_portion(120, "g", [])
    assert grams.grams == 120
    ounces = resolve_portion(2, "oz", [])
    assert ounces.grams == 2 * 28.349523125


def test_household_measure_and_branded_serving():
    measures = [
        HouseholdMeasure(id="m0", label="1 sandwich", grams=198),
        HouseholdMeasure(id="m1", label="1 slice", grams=28),
    ]
    sandwich = resolve_portion(1, "sandwich", measures)
    assert sandwich.grams == 198
    two = resolve_portion(2, "slice", measures)
    assert two.grams == 56
    serving = resolve_portion(1, "serving", [HouseholdMeasure(id="serving", label="1 bar", grams=40)])
    assert serving.grams == 40


def test_no_measure_is_free_text_not_invented_chips():
    decision = resolve_portion(None, None, [])
    assert decision.grams is None
    assert decision.chips == []
    assert decision.free_text is True


def test_real_measures_become_chips_when_amount_missing():
    measures = [HouseholdMeasure(id="m0", label="1 large", grams=50)]
    decision = resolve_portion(None, None, measures)
    assert decision.grams is None
    assert decision.chips == measures
    assert decision.free_text is False


def test_stated_egg_count_does_not_use_a_tablespoon():
    measures = [HouseholdMeasure(id="serving", label="3 Tbsp", grams=47)]
    decision = resolve_portion(2, "whole eggs", measures)
    assert decision.grams is None
    assert decision.chips == []
    assert decision.free_text is True


def test_suggestion_caps_oil_at_two_tablespoons():
    tbsp = HouseholdMeasure(id="tbsp", label="1 tablespoon", grams=13.5)
    grams, label, condiment = suggestion_portion(
        200,
        kcal_per_100g=884,
        family="oil",
        measures=[tbsp],
        portion_label="200 ml (200 g)",
    )
    assert condiment is True
    assert grams == 27.0
    assert "2 Tbsp" in (label or "")


def test_suggestion_keeps_a_normal_egg_serving():
    grams, label, condiment = suggestion_portion(
        100,
        kcal_per_100g=155,
        family="egg",
        measures=[HouseholdMeasure(id="m0", label="1 large", grams=50)],
        portion_label="2 large (100 g)",
    )
    assert condiment is False
    assert grams == 100
    assert label == "2 large (100 g)"
