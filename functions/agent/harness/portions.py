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
        # "2 whole eggs" must not become the listing's tablespoon.
        return PortionDecision(grams=None, label=None, chips=[], free_text=True)

    if quantity is not None and quantity > 0 and (not raw_unit or raw_unit in _COUNT_UNITS):
        if len(known) == 1:
            grams = float(quantity) * _per_one(known[0])
            return PortionDecision(
                grams=grams,
                label=f"{_fmt_grams(float(quantity))} {known[0].label} ({_fmt_grams(grams)} g)",
            )
        return PortionDecision(grams=None, label=None, chips=known, free_text=not known)

    return PortionDecision(grams=None, label=None, chips=known, free_text=not known)


_CONDIMENT_KCAL = 500.0
_CONDIMENT_FAMILIES = {"oil", "fat", "butter", "lard"}
_MAX_PLATE_G = 500.0
_MAX_HOUSEHOLD = 3.0


def is_condiment(*, kcal_per_100g: float, family: str = "") -> bool:
    blob = (family or "").strip().lower()
    return float(kcal_per_100g) >= _CONDIMENT_KCAL or blob in _CONDIMENT_FAMILIES


def _named_measure(measures: list[HouseholdMeasure], *needles: str) -> HouseholdMeasure | None:
    for measure in measures:
        label = (measure.label or "").lower()
        if any(needle in label for needle in needles):
            return measure
    return None


def _measure_unit_name(label: str) -> str:
    low = (label or "").lower()
    if "tablespoon" in low or re.search(r"\btbsp\b", low):
        return "Tbsp"
    if "teaspoon" in low or re.search(r"\btsp\b", low):
        return "tsp"
    if "cup" in low:
        return "cup"
    stripped = re.sub(r"^\s*\d+(?:\.\d+)?\s*", "", label or "").strip()
    return stripped or (label or "serving")


def _pick_measure(known: list[HouseholdMeasure], *, condiment: bool) -> HouseholdMeasure | None:
    if condiment:
        return _named_measure(known, "tablespoon", "tbsp") or _named_measure(known, "teaspoon", "tsp")
    return (
        _named_measure(known, "serving")
        or _named_measure(known, "large", "medium", "small", "piece", "slice", "whole")
        or _named_measure(known, "cup")
    )


def _snap_household(
    grams: float,
    measure: HouseholdMeasure,
    *,
    max_count: float,
) -> tuple[float, str] | None:
    unit = _per_one(measure)
    if unit <= 0:
        return None
    count = round(float(grams) / unit * 2.0) / 2.0
    if count <= 0:
        count = 1.0
    count = min(count, max_count)
    sized = count * unit
    if grams > 0 and abs(sized - grams) / grams > 0.2 and count != max_count:
        return None
    name = _measure_unit_name(measure.label)
    return sized, f"{_fmt_grams(count)} {name} ({_fmt_grams(sized)} g)"


def suggestion_portion(
    grams: float,
    *,
    kcal_per_100g: float,
    family: str = "",
    measures: list[HouseholdMeasure] | None = None,
    portion_label: str | None = None,
) -> tuple[float, str | None, bool]:
    """Cap a suggested item at a serving a person would eat. Remaining kcal is not a fill target.

    Returns (grams, label, is_condiment). Oils/fats cap at ~2 tbsp. Staples cap at 3 cups/servings
    or 500 g. Labels prefer household measures (2 large, 1 cup, 1 Tbsp).
    """
    known = [m for m in (measures or []) if m.grams and m.grams > 0]
    condiment = is_condiment(kcal_per_100g=kcal_per_100g, family=family)
    grams = float(grams)
    if condiment:
        tbsp = _named_measure(known, "tablespoon", "tbsp")
        unit_g = _per_one(tbsp) if tbsp else SWIFT_PARITY_GRAMS["tablespoon"]
        cap = 2.0 * unit_g
        if grams > cap + 0.5:
            grams = cap
        snapped = _snap_household(grams, tbsp, max_count=2.0) if tbsp else None
        if snapped is None:
            fake = HouseholdMeasure(id="tbsp", label="1 tablespoon", grams=unit_g)
            snapped = _snap_household(grams, fake, max_count=2.0)
        if snapped:
            return snapped[0], snapped[1], True
        return grams, f"{_fmt_grams(2)} Tbsp ({_fmt_grams(grams)} g)", True

    cup = _named_measure(known, "cup")
    serving = _named_measure(known, "serving")
    if cup:
        cap = _MAX_HOUSEHOLD * _per_one(cup)
        if grams > cap + 1:
            grams = cap
    elif serving:
        cap = _MAX_HOUSEHOLD * _per_one(serving)
        if grams > cap + 1:
            grams = cap
    elif grams > _MAX_PLATE_G:
        grams = _MAX_PLATE_G

    picked = _pick_measure(known, condiment=False)
    if picked is not None:
        snapped = _snap_household(grams, picked, max_count=_MAX_HOUSEHOLD)
        if snapped:
            return snapped[0], snapped[1], False
    if portion_label:
        return grams, portion_label, False
    return grams, f"{_fmt_grams(grams)} g", False

