"""Open Food Facts barcode lookup — exact GTIN only; never invent macros."""

from __future__ import annotations

import re
from typing import Any, Optional

import httpx

from schemas import MacroTotals

OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
USER_AGENT = "Capy/1.0 (https://github.com/sagban/capy)"
_TIMEOUT = 8.0

_DIGITS = re.compile(r"\D+")
_SERVING_G = re.compile(
    r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>g|gr|gram|grams|ml|milliliter|milliliters)\b",
    re.I,
)


def normalize_gtin(raw: str) -> str:
    """Keep digits only; drop empty."""
    return _DIGITS.sub("", (raw or "").strip())


def gtin_lookup_candidates(gtin: str) -> list[str]:
    """UPC-A (12) ↔ EAN-13 (leading zero) variants for OFF."""
    code = normalize_gtin(gtin)
    if not code:
        return []
    seen: set[str] = set()
    out: list[str] = []

    def add(c: str) -> None:
        if c and c not in seen:
            seen.add(c)
            out.append(c)

    add(code)
    if len(code) == 12:
        add("0" + code)
    elif len(code) == 13 and code.startswith("0"):
        add(code[1:])
    # Also try stripping leading zeros for short retail codes (keep ≥8).
    stripped = code.lstrip("0")
    if len(stripped) >= 8:
        add(stripped)
        if len(stripped) == 12:
            add("0" + stripped)
    return out


def _float_nutrient(nutriments: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        raw = nutriments.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _macros_from_nutriments(nutriments: dict[str, Any]) -> Optional[MacroTotals]:
    calories = _float_nutrient(
        nutriments,
        "energy-kcal_100g",
        "energy-kcal_value",
        "energy-kcal",
    )
    if calories is None:
        # OFF sometimes only has kJ.
        kj = _float_nutrient(nutriments, "energy-kj_100g", "energy_100g")
        if kj is not None:
            calories = kj / 4.184
    protein = _float_nutrient(nutriments, "proteins_100g", "protein_100g")
    carbs = _float_nutrient(nutriments, "carbohydrates_100g", "carbohydrate_100g")
    fat = _float_nutrient(nutriments, "fat_100g")

    if calories is None:
        return None
    macros = [protein, carbs, fat]
    if all(m is None for m in macros):
        return None
    return MacroTotals(
        calories=float(calories),
        proteinG=float(protein or 0),
        carbsG=float(carbs or 0),
        fatG=float(fat or 0),
    )


def _parse_serving_grams(product: dict[str, Any]) -> tuple[Optional[float], str]:
    """Return (grams, label) when serving size is parseable as g/ml (~1 g/ml)."""
    label = str(product.get("serving_size") or "").strip()
    qty = product.get("serving_quantity")
    unit = str(product.get("serving_quantity_unit") or "").strip().lower()

    if qty is not None and unit in {"g", "gr", "gram", "grams", "ml", "milliliter", "milliliters"}:
        try:
            grams = float(qty)
            if grams > 0:
                return grams, label or f"{grams:g} {unit}"
        except (TypeError, ValueError):
            pass

    if label:
        match = _SERVING_G.search(label.replace(",", "."))
        if match:
            try:
                grams = float(match.group("qty").replace(",", "."))
                if grams > 0:
                    return grams, label
            except ValueError:
                pass
    return None, label


def _display_name(product: dict[str, Any]) -> str:
    for key in ("product_name", "product_name_en", "generic_name", "generic_name_en"):
        name = str(product.get(key) or "").strip()
        if name:
            return name
    return ""


def _brand(product: dict[str, Any]) -> str:
    brands = str(product.get("brands") or "").strip()
    if brands:
        return brands.split(",")[0].strip()
    return str(product.get("brand_owner") or "").strip()


def map_product(code: str, product: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Map an OFF product payload to the lookup_barcode hit shape, or None if unusable."""
    per100g = _macros_from_nutriments(dict(product.get("nutriments") or {}))
    if per100g is None:
        return None
    name = _display_name(product)
    if not name:
        return None
    serving_g, serving_label = _parse_serving_grams(product)
    hit: dict[str, Any] = {
        "found": True,
        "foodId": f"off_{code}",
        "displayName": name,
        "per100g": per100g.model_dump(),
        "source": "open_food_facts",
    }
    brand = _brand(product)
    if brand:
        hit["brand"] = brand
    if serving_g is not None:
        hit["servingGrams"] = serving_g
    if serving_label:
        hit["servingLabel"] = serving_label
    return hit


def fetch_product(code: str, *, client: Optional[httpx.Client] = None) -> Optional[dict[str, Any]]:
    url = OFF_PRODUCT_URL.format(code=code)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    own_client = client is None
    http = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = http.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    finally:
        if own_client:
            http.close()

    if int(data.get("status") or 0) != 1:
        return None
    product = data.get("product")
    if not isinstance(product, dict):
        return None
    return product


def lookup_barcode(gtin: str, *, client: Optional[httpx.Client] = None) -> dict[str, Any]:
    """Exact GTIN lookup. Returns found hit or {found: false}."""
    for code in gtin_lookup_candidates(gtin):
        product = fetch_product(code, client=client)
        if product is None:
            continue
        hit = map_product(code, product)
        if hit is not None:
            return hit
    return {"found": False}
