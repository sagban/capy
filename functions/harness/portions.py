"""Turn a quantity and unit into grams.

Factors for g/ml/oz/tsp/tbsp/cup match `PortionUnit.gramsPerUnit` in
`capy/Core/Units.swift`. Household chips come only from the food's own measures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from schemas import HouseholdMeasure

# 1 unit → grams. `serving` is food-specific and is not listed here.
SWIFT_PARITY_GRAMS: dict[str, float] = {
    "gram": 1.0,
    "milliliter": 1.0,
    "ounce": 28.349523125,
    "teaspoon": 4.92892,
    "tablespoon": 14.7868,
    "cup": 236.588,
}

_UNIT_ALIASES: dict[str, str] = {
    "g": "gram",
    "gram": "gram",
    "grams": "gram",
    "ml": "milliliter",
    "milliliter": "milliliter",
    "milliliters": "milliliter",
    "oz": "ounce",
    "ounce": "ounce",
    "ounces": "ounce",
    "tsp": "teaspoon",
    "teaspoon": "teaspoon",
    "teaspoons": "teaspoon",
    "tbsp": "tablespoon",
    "tablespoon": "tablespoon",
    "tablespoons": "tablespoon",
    "cup": "cup",
    "cups": "cup",
}

_COUNT_UNITS = {"", "count", "piece", "pieces", "x", "item", "items"}
_SERVING_UNITS = {"serving", "servings"}


@dataclass
class PortionDecision:
    grams: float | None
    label: str | None
    chips: list[HouseholdMeasure] = field(default_factory=list)
    free_text: bool = False


def _norm_unit(unit: str | None) -> str:
    return re.sub(r"[^a-z]", "", (unit or "").lower())


def _lead_count(label: str) -> float:
    match = re.match(r"\s*(\d+(?:\.\d+)?)", label or "")
    if not match:
        return 1.0
    value = float(match.group(1))
    return value if value > 0 else 1.0


def _per_one(measure: HouseholdMeasure) -> float:
    return float(measure.grams) / _lead_count(measure.label)


def _match_measure(unit: str, measures: list[HouseholdMeasure]) -> HouseholdMeasure | None:
    needle = _norm_unit(unit)
    if not needle:
        return None
    for measure in measures:
        label = _norm_unit(measure.label)
        if not label:
            continue
        if needle == label or needle in label or label.endswith(needle):
            return measure
    return None


def _fmt_grams(grams: float) -> str:
    if abs(grams - round(grams)) < 0.05:
        return str(int(round(grams)))
    return f"{grams:.1f}"


def resolve_portion(
    quantity: float | None,
    unit: str | None,
    measures: list[HouseholdMeasure] | None,
) -> PortionDecision:
    """Return grams, or chips / a free-text grams field when the amount is unknown."""
    known = [m for m in (measures or []) if m.grams and m.grams > 0]
    raw_unit = (unit or "").strip().lower()
    canonical = _UNIT_ALIASES.get(_norm_unit(raw_unit))

    if quantity is not None and quantity > 0 and canonical:
        grams = float(quantity) * SWIFT_PARITY_GRAMS[canonical]
        label_unit = raw_unit or canonical
        return PortionDecision(grams=grams, label=f"{_fmt_grams(float(quantity))} {label_unit} ({_fmt_grams(grams)} g)")

    if quantity is not None and quantity > 0 and raw_unit in _SERVING_UNITS:
        serving = next((m for m in known if "serving" in m.label.lower() or m.id == "serving"), None)
        if serving is None and len(known) == 1:
            serving = known[0]
        if serving is not None:
            grams = float(quantity) * _per_one(serving)
            return PortionDecision(
                grams=grams,
                label=f"{_fmt_grams(float(quantity))} {serving.label} ({_fmt_grams(grams)} g)",
            )
        return PortionDecision(grams=None, label=None, chips=known, free_text=not known)

    if quantity is not None and quantity > 0 and raw_unit and raw_unit not in _COUNT_UNITS:
        matched = _match_measure(raw_unit, known)
        if matched is not None:
            grams = float(quantity) * _per_one(matched)
            return PortionDecision(
                grams=grams,
                label=f"{_fmt_grams(float(quantity))} {matched.label} ({_fmt_grams(grams)} g)",
            )
        return PortionDecision(grams=None, label=None, chips=known, free_text=not known)

    if quantity is not None and quantity > 0 and (not raw_unit or raw_unit in _COUNT_UNITS):
        if len(known) == 1:
            grams = float(quantity) * _per_one(known[0])
            return PortionDecision(
                grams=grams,
                label=f"{_fmt_grams(float(quantity))} {known[0].label} ({_fmt_grams(grams)} g)",
            )
        return PortionDecision(grams=None, label=None, chips=known, free_text=not known)

    return PortionDecision(grams=None, label=None, chips=known, free_text=not known)
