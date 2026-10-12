#!/usr/bin/env python3
"""Build Capy food catalog from USDA Foundation + SR Legacy downloads.

Downloads (if missing), extracts energy/PCF per 100g, writes compact JSON for
iOS + Functions. Merges CatalogOverlay.json for Indian/custom foods & composites.

Usage:
  python3 scripts/build_food_catalog.py
  python3 scripts/build_food_catalog.py --skip-download
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "scripts" / "data" / "usda"
OVERLAY = ROOT / "capy" / "Resources" / "CatalogOverlay.json"
OUT_APP = ROOT / "capy" / "Resources" / "SeedFoods.json"
OUT_FN = ROOT / "functions" / "seed" / "SeedFoods.json"

FOUNDATION_URL = (
    "https://fdc.nal.usda.gov/fdc-datasets/"
    "FoodData_Central_foundation_food_json_2026-04-30.zip"
)
SR_LEGACY_URL = (
    "https://fdc.nal.usda.gov/fdc-datasets/"
    "FoodData_Central_sr_legacy_food_json_2018-04.zip"
)

# FDC nutrient ids (preferred) / numbers
NUTRIENT_KCAL = {1008, "1008", "208"}
NUTRIENT_PROTEIN = {1003, "1003", "203"}
NUTRIENT_CARBS = {1005, "1005", "205"}
NUTRIENT_FAT = {1004, "1004", "204"}

CATEGORY_FAMILY = [
    (re.compile(r"poultry|chicken|turkey|duck", re.I), "poultry"),
    (re.compile(r"\bfish\b|shellfish|finfish|seafood", re.I), "fish"),
    (re.compile(r"beef|pork|lamb|veal|game|sausage|meat", re.I), "meat"),
    (re.compile(r"\begg\b", re.I), "egg"),
    (re.compile(r"dairy|milk|cheese|yogurt|butter", re.I), "dairy"),
    (re.compile(r"legume|bean|pea|lentil|soy", re.I), "legume"),
    (re.compile(r"nut|seed", re.I), "nut"),
    (re.compile(r"fruit", re.I), "fruit"),
    (re.compile(r"vegetable|veg", re.I), "veg"),
    (re.compile(r"cereal|grain|pasta|bread|baked|rice|wheat|oat", re.I), "grain"),
    (re.compile(r"fat|oil", re.I), "fat"),
    (re.compile(r"beverage|alcohol", re.I), "beverage"),
    (re.compile(r"spice|herb", re.I), "spice"),
    (re.compile(r"sweet|sugar|candy|dessert", re.I), "sweet"),
]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"cached {dest.name}")
        return
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, dest)


def unzip(zip_path: Path, dest_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
        names = [n for n in zf.namelist() if n.endswith(".json")]
    if not names:
        raise FileNotFoundError(f"no json in {zip_path}")
    return dest_dir / names[0]


def nutrient_amount(food: dict, ids: set) -> float | None:
    for n in food.get("foodNutrients") or []:
        nutrient = n.get("nutrient") or {}
        nid = nutrient.get("id")
        number = nutrient.get("number")
        if nid in ids or number in ids or str(nid) in ids or str(number) in ids:
            amount = n.get("amount")
            if amount is None:
                amount = n.get("median")
            if amount is None:
                continue
            return float(amount)
    return None


def family_for(food: dict) -> str:
    cat = food.get("foodCategory") or {}
    blob = f"{cat.get('description', '')} {food.get('description', '')}"
    for pattern, family in CATEGORY_FAMILY:
        if pattern.search(blob):
            return family
    return "other"


def convert_food(food: dict | None, source: str) -> dict | None:
    if not food or not isinstance(food, dict):
        return None
    kcal = nutrient_amount(food, NUTRIENT_KCAL)
    protein = nutrient_amount(food, NUTRIENT_PROTEIN)
    carbs = nutrient_amount(food, NUTRIENT_CARBS)
    fat = nutrient_amount(food, NUTRIENT_FAT)
    # Require energy; fill missing macros with 0 only if energy present
    if kcal is None:
        return None
    fdc_id = food.get("fdcId")
    if fdc_id is None:
        return None
    name = (food.get("description") or "").strip()
    if not name:
        return None
    return {
        "id": f"usda_{fdc_id}",
        "name": name,
        "family": family_for(food),
        "per100g": {
            "calories": round(kcal, 2),
            "proteinG": round(protein or 0.0, 2),
            "carbsG": round(carbs or 0.0, 2),
            "fatG": round(fat or 0.0, 2),
        },
        "aliases": [],
        "usdaFdcId": int(fdc_id),
        "source": source,
    }


def load_foundation(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    foods = data.get("FoundationFoods") or []
    out = []
    for food in foods:
        converted = convert_food(food, "usda_foundation")
        if converted:
            out.append(converted)
    return out


def load_sr_legacy(path: Path) -> list[dict]:
    try:
        import ijson
    except ImportError:
        print("installing ijson…", file=sys.stderr)
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ijson"])
        import ijson

    out = []
    with path.open("rb") as f:
        for food in ijson.items(f, "SRLegacyFoods.item"):
            converted = convert_food(food, "usda_sr_legacy")
            if converted:
                out.append(converted)
    return out


def resolve_food_id(ref: str, by_name: dict[str, str], by_id: dict[str, dict]) -> str | None:
    if ref.startswith("resolve:"):
        name = ref[len("resolve:") :].strip().lower()
        if name in by_name:
            return by_name[name]
        # substring fallback
        for key, food_id in by_name.items():
            if name in key or key in name:
                return food_id
        return None
    if ref in by_id:
        return ref
    return None


def merge_overlay(foods: list[dict], overlay: dict) -> tuple[list[dict], list, list]:
    by_id = {f["id"]: f for f in foods}
    for food in overlay.get("foods") or []:
        by_id[food["id"]] = food

    by_name = {f["name"].strip().lower(): f["id"] for f in by_id.values()}

    composites = []
    for composite in overlay.get("composites") or []:
        components = []
        ok = True
        for component in composite.get("components") or []:
            resolved = resolve_food_id(component["foodId"], by_name, by_id)
            if not resolved:
                print(f"  WARN unresolved component {component['foodId']} in {composite['id']}")
                ok = False
                break
            components.append({"foodId": resolved, "grams": component["grams"]})
        if ok and components:
            composites.append({**composite, "components": components})

    templates = overlay.get("templates") or []
    merged = sorted(
        by_id.values(),
        key=lambda f: (0 if str(f["id"]).startswith("seed_") else 1, f["name"].lower()),
    )
    return merged, composites, templates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    foundation_zip = DATA / "foundation.zip"
    sr_zip = DATA / "sr_legacy.zip"

    if not args.skip_download:
        download(FOUNDATION_URL, foundation_zip)
        download(SR_LEGACY_URL, sr_zip)

    foundation_json = DATA / "FoodData_Central_foundation_food_json_2026-04-30.json"
    sr_json = DATA / "FoodData_Central_sr_legacy_food_json_2018-04.json"
    if not foundation_json.exists():
        foundation_json = unzip(foundation_zip, DATA)
    if not sr_json.exists():
        sr_json = unzip(sr_zip, DATA)

    print("converting Foundation…")
    foundation = load_foundation(foundation_json)
    print(f"  {len(foundation)} foods")

    print("converting SR Legacy (stream)…")
    sr = load_sr_legacy(sr_json)
    print(f"  {len(sr)} foods")

    # Foundation wins on duplicate fdcId (shouldn't overlap often)
    by_id = {f["id"]: f for f in sr}
    by_id.update({f["id"]: f for f in foundation})

    overlay = {"foods": [], "composites": [], "templates": []}
    if OVERLAY.exists():
        overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
        print(f"overlay foods={len(overlay.get('foods') or [])}")

    foods, composites, templates = merge_overlay(list(by_id.values()), overlay)

    catalog = {
        "version": 2,
        "source": {
            "foundation": "FoodData_Central_foundation_food_json_2026-04-30",
            "srLegacy": "FoodData_Central_sr_legacy_food_json_2018-04",
            "overlay": "CatalogOverlay.json",
        },
        "foods": foods,
        "composites": composites,
        "templates": templates,
    }

    text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    OUT_APP.parent.mkdir(parents=True, exist_ok=True)
    OUT_FN.parent.mkdir(parents=True, exist_ok=True)
    OUT_APP.write_text(text + "\n", encoding="utf-8")
    OUT_FN.write_text(text + "\n", encoding="utf-8")
    mb = OUT_APP.stat().st_size / (1024 * 1024)
    print(f"wrote {OUT_APP.relative_to(ROOT)} ({mb:.1f} MB, {len(foods)} foods)")
    print(f"wrote {OUT_FN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
