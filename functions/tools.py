"""Request-scoped tool implementations for the meal harness."""

from __future__ import annotations

from typing import Any

from catalog import get_food, search_seed, templates
from schemas import FoodHit, InterpretMealRequest
from usda import search_usda

# Process-local same-day miss cache: (dayKey, normalizedQuery) -> True
_MISS_CACHE: set[tuple[str, str]] = set()


def normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def get_user_preferences(req: InterpretMealRequest) -> dict[str, Any]:
    snap = req.memorySnapshot
    return {
        "likes": list(req.preferenceContext.likes or (snap.preferences if snap else [])),
        "dislikes": list(req.preferenceContext.dislikes or (snap.dislikes if snap else [])),
    }


def get_dietary_restrictions(req: InterpretMealRequest) -> dict[str, Any]:
    snap = req.memorySnapshot
    return {
        "allergies": list(req.preferenceContext.allergies or (snap.allergies if snap else [])),
        "diets": list(req.preferenceContext.diets or (snap.diets if snap else [])),
    }


def get_long_term_memory(req: InterpretMealRequest) -> dict[str, Any]:
    return {
        "notes": [{"id": n.id, "text": n.text} for n in req.longTermMemory],
    }


def get_today_food_log(req: InterpretMealRequest) -> dict[str, Any]:
    return {
        "dayKey": req.dayKey,
        "entries": [e.model_dump() for e in req.diaryContext.today],
    }


def get_previous_food_logs(req: InterpretMealRequest) -> dict[str, Any]:
    return {
        "days": [d.model_dump() for d in req.diaryContext.previousDays],
    }


def search_food(req: InterpretMealRequest, query: str, limit: int = 10) -> dict[str, Any]:
    norm = normalize_query(query)
    cache_key = (req.dayKey, norm)
    if cache_key in _MISS_CACHE:
        return {"results": [], "cache": "miss"}

    hits = search_seed(query, limit=limit)
    cache = "hit" if hits else "miss"
    if not hits:
        usda_hits = search_usda(query, limit=min(5, limit))
        if usda_hits:
            hits = usda_hits
            cache = "usda"
        else:
            _MISS_CACHE.add(cache_key)
            return {"results": [], "cache": "miss"}

    diets = set(d.lower() for d in get_dietary_restrictions(req)["diets"])
    if "vegetarian" in diets or "vegan" in diets:
        blocked = {"poultry", "fish", "meat", "beef", "pork"}
        if "vegan" in diets:
            blocked |= {"dairy", "egg"}
        hits = [h for h in hits if h.family.lower() not in blocked]

    return {
        "results": [
            {
                "foodId": h.foodId,
                "displayName": h.displayName,
                "source": h.source,
                "per100g": h.per100g.model_dump(),
                "family": h.family,
            }
            for h in hits[:limit]
        ],
        "cache": cache,
    }


def _diet_blocks_food(food: FoodHit, diets: set[str]) -> bool:
    family = food.family.lower()
    name = food.displayName.lower()
    food_id = food.foodId.lower()
    if "vegetarian" in diets or "vegan" in diets:
        if family in {"poultry", "fish", "meat", "beef", "pork"}:
            return True
        if any(token in name or token in food_id for token in ("chicken", "salmon", "beef", "pork", "fish")):
            return True
        # Composite ids that embed animal foods (e.g. seed_chicken_stirfry)
        if "chicken" in food_id or "salmon" in food_id:
            return True
    if "vegan" in diets and family in {"dairy", "egg"}:
        return True
    return False


def propose_meal(req: InterpretMealRequest) -> dict[str, Any]:
    """Propose a template that fits diets; does not compute trusted meal macros for UI."""
    diets = {d.lower() for d in get_dietary_restrictions(req)["diets"]}
    today_names = {e.name.lower() for e in req.diaryContext.today}
    candidates = []
    for tpl in templates():
        items = []
        blocked = False
        for item in tpl.get("items", []):
            food = get_food(item["foodId"])
            if not food:
                continue
            if _diet_blocks_food(food, diets):
                blocked = True
                break
            items.append(
                {
                    "foodId": food.foodId,
                    "displayName": food.displayName,
                    "grams": item.get("grams"),
                    "confidence": 0.7,
                }
            )
        if blocked or not items:
            continue
        # Soft variety: skip if template name already logged today
        if tpl["name"].lower() in today_names:
            continue
        candidates.append(
            {
                "templateId": tpl["id"],
                "name": tpl["name"],
                "items": items,
            }
        )
    if not candidates and templates():
        # Fall back to first non-blocked
        for tpl in templates():
            items = []
            ok = True
            for item in tpl.get("items", []):
                food = get_food(item["foodId"])
                if not food:
                    continue
                if _diet_blocks_food(food, diets):
                    ok = False
                    break
                items.append(
                    {
                        "foodId": food.foodId,
                        "displayName": food.displayName,
                        "grams": item.get("grams"),
                        "confidence": 0.55,
                    }
                )
            if ok and items:
                candidates.append(
                    {"templateId": tpl["id"], "name": tpl["name"], "items": items}
                )
                break
    return {"proposals": candidates[:3]}


def clear_miss_cache() -> None:
    _MISS_CACHE.clear()


TOOL_HANDLERS = {
    "get_user_preferences": lambda req, **_: get_user_preferences(req),
    "get_dietary_restrictions": lambda req, **_: get_dietary_restrictions(req),
    "get_long_term_memory": lambda req, **_: get_long_term_memory(req),
    "get_today_food_log": lambda req, **_: get_today_food_log(req),
    "get_previous_food_logs": lambda req, **_: get_previous_food_logs(req),
    "search_food": lambda req, query="", limit=10, **_: search_food(req, query, limit),
    "propose_meal": lambda req, **_: propose_meal(req),
}


def run_tool(name: str, req: InterpretMealRequest, **kwargs: Any) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": f"unknown_tool:{name}"}
    return handler(req, **kwargs)
