"""Open Food Facts barcode mapper + lookup_barcode candidates."""

from __future__ import annotations

import json
from pathlib import Path

from agent.tools.search.open_food_facts import (
    gtin_lookup_candidates,
    lookup_barcode,
    map_product,
    normalize_gtin,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_normalize_gtin_strips_noise():
    assert normalize_gtin(" 0123-4567-8905 ") == "012345678905"
    assert normalize_gtin("") == ""


def test_gtin_candidates_upc_ean():
    cands = gtin_lookup_candidates("3017620422003")
    assert cands[0] == "3017620422003"
    upc = gtin_lookup_candidates("012345678905")
    assert "012345678905" in upc
    assert "0012345678905" in upc or "0" + "012345678905" in upc


def test_map_product_hit():
    data = _load("off_product_hit.json")
    hit = map_product(data["code"], data["product"])
    assert hit is not None
    assert hit["found"] is True
    assert hit["foodId"] == "off_3017620422003"
    assert hit["displayName"] == "Nutella"
    assert hit["brand"] == "Ferrero"
    assert hit["source"] == "open_food_facts"
    assert hit["servingGrams"] == 15
    assert hit["per100g"]["calories"] == 539
    assert hit["per100g"]["proteinG"] == 6.3
    assert hit["per100g"]["carbsG"] == 57.5
    assert hit["per100g"]["fatG"] == 30.9


def test_map_product_incomplete_macros():
    data = _load("off_product_incomplete.json")
    assert map_product(data["code"], data["product"]) is None


def test_lookup_barcode_miss_status_zero(monkeypatch):
    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": 0, "status_verbose": "product not found"}

    class _Client:
        def get(self, url: str, headers: dict | None = None):  # noqa: ARG002
            return _Resp()

        def close(self) -> None:
            return None

    result = lookup_barcode("9999999999999", client=_Client())
    assert result == {"found": False}


def test_lookup_barcode_hit_via_client(monkeypatch):
    data = _load("off_product_hit.json")

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return data

    class _Client:
        def get(self, url: str, headers: dict | None = None):  # noqa: ARG002
            return _Resp()

        def close(self) -> None:
            return None

    result = lookup_barcode("3017620422003", client=_Client())
    assert result["found"] is True
    assert result["displayName"] == "Nutella"
