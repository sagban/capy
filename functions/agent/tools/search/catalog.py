"""Embedded seed catalog for Functions (mirrors capy/Resources/SeedFoods.json)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from schemas import FoodHit, MacroTotals

_NOISE = (
    "babyfood",
    "baby food",
    "infant",
    "toddler",
    "junior",
    "alcoholic",
    "sake",
    "cereals ready-to-eat",
    "frozen entree",
    "fast foods",
    "restaurant",
    "applebee",
    "mcdonald",
    "pizza hut",
    "wendy",
    "burger king",
    "subway",
    "domino",
    "taco bell",
    "snacks,",
    "beverages,",
    "candy",
    "candies,",
    "pie,",
    "cookies",
    "imitation",
)

# …/functions/agent/tools/search/catalog.py → functions = parents[3], repo = parents[4]
_FUNCTIONS_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SEED_CANDIDATES = [
    _FUNCTIONS_ROOT / "seed" / "SeedFoods.json",
    _REPO_ROOT / "capy" / "Resources" / "SeedFoods.json",
    _REPO_ROOT / "docs" / "seed" / "SeedFoods.draft.json",
]


@lru_cache(maxsize=1)
def load_seed() -> dict:
    for path in _SEED_CANDIDATES:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {"version": 1, "foods": [], "composites": [], "templates": []}


def all_food_hits() -> list[FoodHit]:
    seed = load_seed()
    hits: list[FoodHit] = []
    by_id: dict[str, FoodHit] = {}
    for food in seed.get("foods", []):
        per = food["per100g"]
        hit = FoodHit(
            foodId=food["id"],
            displayName=food["name"],
            source="seed",
            per100g=MacroTotals(**per),
            family=food.get("family", ""),
        )
        hits.append(hit)
        by_id[hit.foodId] = hit

    for composite in seed.get("composites", []):
        totals = MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
        grams_total = 0.0
        for component in composite.get("components", []):
            base = by_id.get(component["foodId"])
            if not base:
                continue
            g = float(component["grams"])
            factor = g / 100.0
            totals = MacroTotals(
                calories=totals.calories + base.per100g.calories * factor,
                proteinG=totals.proteinG + base.per100g.proteinG * factor,
                carbsG=totals.carbsG + base.per100g.carbsG * factor,
                fatG=totals.fatG + base.per100g.fatG * factor,
            )
            grams_total += g
        if grams_total > 0:
            f = 100.0 / grams_total
            per100 = MacroTotals(
                calories=totals.calories * f,
                proteinG=totals.proteinG * f,
                carbsG=totals.carbsG * f,
                fatG=totals.fatG * f,
            )
        else:
            per100 = MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
        hit = FoodHit(
            foodId=composite["id"],
            displayName=composite["name"],
            source="seed",
            per100g=per100,
            family="composite",
        )
        hits.append(hit)
        by_id[hit.foodId] = hit
    return hits


def _whole_word(query: str, name: str) -> bool:
    return re.search(rf"(^|[\s,/(-]){re.escape(query)}($|[\s,)/])", name) is not None


def _rank_key(name: str, aliases: list[str], family: str, food_id: str, q: str) -> tuple:
    n = name.lower()
    alias_list = [a.lower() for a in aliases]
    fam = family.lower()

    plural = q + "s"
    if n == q or n == plural or q in alias_list:
        match = 0
    elif n.startswith(q + ",") or n.startswith(plural + ","):
        # USDA staple pattern: "Rice, white, …" / "Bananas, raw"
        match = 1
    elif n.startswith(q + " ") or n.startswith(plural + " "):
        match = 2
    elif any(a == q or a.startswith(q) for a in alias_list):
        match = 3
    elif n.startswith(q) or n.startswith(plural):
        match = 4
    elif _whole_word(q, n) or _whole_word(plural, n):
        match = 5
    elif q in n or any(q in a for a in alias_list):
        match = 6
    elif q in fam:
        match = 7
    else:
        match = 9

    demote = 10 if any(token in n for token in _NOISE) else 0

    # Prefer cooked staples for bare queries; demote bran/flour/mix noise.
    form = 2
    wants_raw = any(tok in q for tok in ("raw", "uncooked", "dry"))
    produce_raw_ok = q in {"banana", "apple", "potato", "milk"}
    if "cooked" in n and not wants_raw:
        form = 0
    elif (wants_raw or produce_raw_ok) and (
        ", raw" in n or "uncooked" in n or n.endswith(", raw") or "fluid" in n
    ):
        form = 0
    elif ", raw" in n or " uncooked" in n or ", dry" in n:
        form = 3
    if any(
        token in n
        for token in (
            " mix",
            "flavor",
            "rice-a-roni",
            "vermicelli mix",
            "bran",
            "flour",
            "cracker",
            "noodles",
            "cereal bar",
            "giblet",
            "gizzard",
            "heart,",
            "liver",
            "neck,",
            "feet,",
            "skin only",
            "capons",
            "stewing",
            "dehydrated",
            "powder",
            "chips",
            "dried",
            "imitation",
            "low sodium",
            "sheep",
            "buffalo",
            "buttermilk",
        )
    ):
        form += 4
    # Prefer the everyday defaults people mean.
    if "long-grain, regular, enriched, cooked" in n:
        form = -1
    elif "chicken, broilers or fryers, breast" in n and "cooked" in n:
        form = -1
    elif n.startswith("egg, whole, cooked"):
        form = -1
    elif n.startswith("bananas, raw") or n.startswith("milk, whole,"):
        form = -1

    source = 0 if food_id.startswith("seed_") else 1
    return (match, demote, form, source, len(n), n)


def _query_matches(q: str, name: str, aliases: list[str], family: str) -> bool:
    """Substring contains is allowed only for queries long enough to avoid 'hi'→chicken."""
    n = name.lower()
    fam = family.lower()
    alias_list = [a.lower() for a in aliases]
    if len(q) < 3:
        plural = q + "s"
        return (
            n == q
            or n == plural
            or n.startswith(q + ",")
            or n.startswith(q + " ")
            or n.startswith(plural + ",")
            or any(a == q or a.startswith(q + " ") or a.startswith(q + ",") for a in alias_list)
            or _whole_word(q, n)
        )
    return q in n or any(q in a for a in alias_list) or q in fam


def _seed_query_variants(query: str) -> list[str]:
    """Logging phrases → USDA/seed naming (kept local to avoid food_search import cycle)."""
    q = query.strip().lower()
    if not q:
        return []
    out = [q]
    alt = re.sub(r"\bwhole\s+eggs?\b", "egg, whole", q)
    if alt != q:
        out.append(alt)
    return out


def search_seed(query: str, limit: int = 10) -> list[FoodHit]:
    raw = query.strip()
    if not raw:
        return all_food_hits()[:limit]
    variants = _seed_query_variants(raw)
    seed = load_seed()
    alias_map: dict[str, list[str]] = {
        f["id"]: [a.lower() for a in f.get("aliases", [])] for f in seed.get("foods", [])
    }
    scored: list[tuple[tuple, FoodHit]] = []
    seen: set[str] = set()
    for hit in all_food_hits():
        name = hit.displayName
        aliases = alias_map.get(hit.foodId, [])
        matched_q = next((vq for vq in variants if _query_matches(vq, name, aliases, hit.family)), None)
        if matched_q is None:
            continue
        if hit.foodId in seen:
            continue
        seen.add(hit.foodId)
        key = _rank_key(name, aliases, hit.family, hit.foodId, matched_q)
        scored.append((key, hit))
    scored.sort(key=lambda x: x[0])
    return [h for _, h in scored[:limit]]


def get_food(food_id: str) -> FoodHit | None:
    for hit in all_food_hits():
        if hit.foodId == food_id:
            return hit
    return None
