"""Density check for cited web nutrition. Arithmetic stays in code."""

from __future__ import annotations


def density_ok(calories: float, protein_g: float, carbs_g: float, fat_g: float) -> bool:
    """Atwater within 15% and at most 900 kcal per 100 g."""
    try:
        kcal = float(calories)
        protein = float(protein_g)
        carbs = float(carbs_g)
        fat = float(fat_g)
    except (TypeError, ValueError):
        return False
    if kcal <= 0 or kcal > 900:
        return False
    if min(protein, carbs, fat) < 0:
        return False
    expected = 4 * protein + 4 * carbs + 9 * fat
    return abs(kcal - expected) <= 0.15 * kcal
