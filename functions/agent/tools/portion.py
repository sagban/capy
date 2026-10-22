"""Quantity and unit to grams. Unknown units stay unmapped."""

from __future__ import annotations

from typing import Any

from agent.harness.portions import resolve_portion
from schemas import HouseholdMeasure


def portion_to_grams(
    quantity: float,
    unit: str | None,
    measures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    parsed = [HouseholdMeasure.model_validate(row) for row in (measures or []) if isinstance(row, dict)]
    decision = resolve_portion(quantity, unit, parsed)
    if decision.grams is None or decision.grams <= 0:
        return {"unmapped": True}
    return {"grams": round(float(decision.grams), 2), "label": decision.label or ""}
