"""Portion grams: Swift unit parity, household measures, free-text when none exist."""

from schemas import HouseholdMeasure

from harness.portions import SWIFT_PARITY_GRAMS, resolve_portion


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
