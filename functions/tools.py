"""Request-scoped tool implementations for the meal harness (ReAct-bound)."""

from __future__ import annotations

from typing import Any

from catalog import all_food_hits, get_food, search_seed, templates
from food_search import search_foods
from schemas import FoodHit, InterpretMealRequest, MacroTotals
from web_search import web_search as _web_search


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
    remaining = req.diaryContext.remaining
    return {
        "dayKey": req.dayKey,
        "entries": [e.model_dump() for e in req.diaryContext.today],
        "remaining": remaining.model_dump(),
    }


def get_previous_food_logs(req: InterpretMealRequest) -> dict[str, Any]:
    return {
        "days": [d.model_dump() for d in req.diaryContext.previousDays],
    }


def search_food(req: InterpretMealRequest, query: str, limit: int = 10) -> dict[str, Any]:
    """Internal search. No miss cache — a later query for the same words must be able to hit."""
    return search_foods(req, query, limit=limit)


def get_food_nutrition(req: InterpretMealRequest, food_id: str = "") -> dict[str, Any]:
    food = get_food(food_id)
    if not food:
        return {"error": "not_found", "foodId": food_id}
    return {
        "foodId": food.foodId,
        "displayName": food.displayName,
        "source": food.source,
        "per100g": food.per100g.model_dump(),
        "family": food.family,
    }


def scale_portion(
    req: InterpretMealRequest,
    food_id: str,
    grams: float,
) -> dict[str, Any]:
    """Deterministic scale — same formula as Swift MacroMath.scale. Grams are required."""
    if grams is None:
        return {"error": "grams_required", "foodId": food_id}
    food = get_food(food_id)
    if not food:
        return {"error": "not_found", "foodId": food_id}
    g = float(grams)
    factor = g / 100.0
    per = food.per100g
    scaled = MacroTotals(
        calories=round(per.calories * factor, 2),
        proteinG=round(per.proteinG * factor, 2),
        carbsG=round(per.carbsG * factor, 2),
        fatG=round(per.fatG * factor, 2),
    )
    return {
        "foodId": food.foodId,
        "displayName": food.displayName,
        "grams": g,
        "per100g": per.model_dump(),
        "scaled": scaled.model_dump(),
        "source": food.source,
    }


def web_search(req: InterpretMealRequest, query: str = "", limit: int = 5) -> dict[str, Any]:
    return _web_search(query, limit=limit)


def _diet_blocks_food(food: FoodHit, diets: set[str]) -> bool:
    family = food.family.lower()
    name = food.displayName.lower()
    food_id = food.foodId.lower()
    if "vegetarian" in diets or "vegan" in diets:
        if family in {"poultry", "fish", "meat", "beef", "pork"}:
            return True
        if any(token in name or token in food_id for token in ("chicken", "salmon", "beef", "pork", "fish")):
            return True
        if "chicken" in food_id or "salmon" in food_id:
            return True
    if "vegan" in diets and family in {"dairy", "egg"}:
        return True
    return False


def propose_meal(req: InterpretMealRequest) -> dict[str, Any]:
    """Propose a template that fits diets; does not invent free-text macros."""
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
                    "per100g": food.per100g.model_dump(),
                }
            )
        if blocked or not items:
            continue
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
                        "per100g": food.per100g.model_dump(),
                    }
                )
            if ok and items:
                candidates.append(
                    {"templateId": tpl["id"], "name": tpl["name"], "items": items}
                )
                break
    return {"proposals": candidates[:3]}


_SUGGEST_BAD_NAME = (
    "babyfood", "infant", "powder", "isolate", "concentrate", "dried", "dehydrated",
    "flour", "oil,", "gelatin", "imitation", "substitute", "separable", "imported",
    "variety meats", "liver", "giblet", "heart,", "kidney", "tongue", "tripe", "brain",
    "alaska native", "game meat", "unprepared", "formula", "supplement", "mix,",
    "applebee", "arby", "mcdonald", "wendy", "burger king", "subway", "taco bell",
    "pizza hut", "domino", "kfc", "chick-fil", "fast foods", "restaurant", "snacks,",
    "candies", "ns as to", "dry mix", "seasoning", "extract", "meal replacement",
)
_SUGGEST_FAMILIES = {"meat", "poultry", "fish", "egg", "dairy", "legume", "grain", "nut", "composite"}
_NEEDS_COOKED = {"meat", "poultry", "fish", "legume", "grain"}


def _suggestable(food: FoodHit) -> bool:
    """Everyday, ready-to-eat-ish foods only (the catalog is a raw USDA dump)."""
    name = food.displayName.lower()
    fam = food.family.lower()
    if food.foodId.startswith("seed_"):
        return fam not in {"supplement"}
    if fam not in _SUGGEST_FAMILIES:
        return False
    if any(tok in name for tok in _SUGGEST_BAD_NAME):
        return False
    if fam in _NEEDS_COOKED and "cooked" not in name:
        return False
    if fam == "egg" and "raw" in name:
        return False
    return name.count(",") <= 4


def find_foods_for_budget(
    req: InterpretMealRequest,
    max_calories: float | None = None,
    min_protein_g: float | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Everyday foods whose portion fits a calorie ceiling and protein floor.

    No arguments -> a sensible NEXT-MEAL share of what's left (not the whole day).
    User-stated numbers override. Portions are deterministic grams; the LLM never
    computes macros. Diet/allergy/dislike filters applied.
    """
    remaining = req.diaryContext.remaining
    if max_calories is None and min_protein_g is None:
        rem_cal = max(float(remaining.calories), 0.0)
        cal_cap = min(rem_cal, max(rem_cal * 0.4, 300.0))
        protein_floor = min(max(float(remaining.proteinG), 0.0) * 0.3, 40.0)
    else:
        cal_cap = float(max_calories) if max_calories else max(float(remaining.calories), 0.0)
        protein_floor = float(min_protein_g) if min_protein_g else 0.0
    if cal_cap <= 0:
        return {"results": [], "budget": {"maxCalories": 0, "minProteinG": protein_floor}, "reason": "no_budget"}

    diets = {d.lower() for d in get_dietary_restrictions(req)["diets"]}
    allergies = [a.lower() for a in get_dietary_restrictions(req)["allergies"] if a]
    dislikes = [d.lower() for d in get_user_preferences(req)["dislikes"] if d]
    likes = [x.lower() for x in get_user_preferences(req)["likes"] if x]
    eaten_today = {e.name.lower() for e in req.diaryContext.today}

    scored: list[tuple[float, FoodHit, dict[str, Any]]] = []
    for food in all_food_hits():
        per = food.per100g
        name = food.displayName.lower()
        if per.calories <= 0 or per.proteinG <= 0 or not _suggestable(food):
            continue
        if _diet_blocks_food(food, diets):
            continue
        if any(a in name for a in allergies) or any(d in name for d in dislikes):
            continue
        if name in eaten_today:
            continue
        grams = 150.0
        if protein_floor > 0:
            grams = protein_floor / per.proteinG * 100.0
        grams = min(max(grams, 40.0), 350.0)
        if per.calories * grams / 100.0 > cal_cap:
            grams = cal_cap / per.calories * 100.0
        grams = max(round(grams / 5.0) * 5.0, 5.0)
        calories = per.calories * grams / 100.0
        protein = per.proteinG * grams / 100.0
        if calories > cal_cap or grams < 40.0:
            continue
        if protein_floor > 0 and protein < protein_floor * 0.9:
            continue
        density = protein / max(calories, 1.0)
        score = density * 60.0 - len(food.displayName) * 0.15
        score += 6.0 if food.foodId.startswith("seed_") else 0.0
        score += 8.0 if any(x in name for x in likes) else 0.0
        scored.append(
            (
                score,
                food,
                {
                    "foodId": food.foodId,
                    "displayName": food.displayName,
                    "grams": grams,
                    "source": food.source,
                    "confidence": 0.7,
                    "per100g": per.model_dump(),
                },
            )
        )
    scored.sort(key=lambda x: -x[0])
    out: list[dict[str, Any]] = []
    per_family: dict[str, int] = {}
    cap = max(1, min(int(limit or 6), 12))
    for _, food, row in scored:
        if per_family.get(food.family, 0) >= 2:
            continue
        per_family[food.family] = per_family.get(food.family, 0) + 1
        out.append(row)
        if len(out) >= cap:
            break
    return {"results": out, "budget": {"maxCalories": cal_cap, "minProteinG": protein_floor}}


def clear_miss_cache() -> None:
    """Kept so older tests can call it. The miss cache is gone."""
    return None


TOOL_HANDLERS = {
    "get_user_preferences": lambda req, **_: get_user_preferences(req),
    "get_dietary_restrictions": lambda req, **_: get_dietary_restrictions(req),
    "get_long_term_memory": lambda req, **_: get_long_term_memory(req),
    "get_today_food_log": lambda req, **_: get_today_food_log(req),
    "get_previous_food_logs": lambda req, **_: get_previous_food_logs(req),
    "search_food": lambda req, query="", limit=10, **_: search_food(req, query, limit),
    "get_food_nutrition": lambda req, food_id="", foodId="", **_: get_food_nutrition(
        req, food_id or foodId
    ),
    "scale_portion": lambda req, food_id="", foodId="", grams=None, **_: (
        scale_portion(req, food_id or foodId, float(grams))
        if grams is not None
        else {"error": "grams_required", "foodId": food_id or foodId}
    ),
    "propose_meal": lambda req, **_: propose_meal(req),
    "find_foods_for_budget": lambda req, maxCalories=None, minProteinG=None, limit=6, **_: find_foods_for_budget(
        req, maxCalories, minProteinG, limit
    ),
    "web_search": lambda req, query="", limit=5, **_: web_search(req, query, limit),
}

TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "get_user_preferences",
        "description": "Get explicit food likes and dislikes.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_dietary_restrictions",
        "description": "Get allergies and diet labels.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_long_term_memory",
        "description": "Get standing notes about the user.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_today_food_log",
        "description": "Today's logged foods and remaining budget (client-computed).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_previous_food_logs",
        "description": "Summaries of previous days' logs.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_food",
        "description": (
            "Multi-source food search (seed + USDA branded/foundation/SR), ranked for logging. "
            "Read confidence + suggestWebSearch. If suggestWebSearch is true, call web_search to "
            "resolve the product (brand nicknames, restaurants), then search_food again with the "
            "label name — never offer mismatched generics for the user to pick."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_food_nutrition",
        "description": "Get per-100g nutrition for a catalog foodId from a prior search.",
        "parameters": {
            "type": "object",
            "properties": {"foodId": {"type": "string"}},
            "required": ["foodId"],
        },
    },
    {
        "name": "scale_portion",
        "description": "Deterministically scale per-100g nutrition to grams.",
        "parameters": {
            "type": "object",
            "properties": {
                "foodId": {"type": "string"},
                "grams": {"type": "number"},
            },
            "required": ["foodId", "grams"],
        },
    },
    {
        "name": "propose_meal",
        "description": "Propose meal templates that fit diet and variety soft rules.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "find_foods_for_budget",
        "description": (
            "Find catalog foods (with portion grams) that fit a calorie ceiling and protein floor. "
            "Call with NO arguments unless the user stated numbers in their message (then pass exactly those); "
            "no arguments gives a sensible next-meal share of what is left, not the whole day. Use for suggest / plan / find requests, then return the best as "
            "candidates. Nutrition is app-owned; do not recite it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "maxCalories": {"type": "number"},
                "minProteinG": {"type": "number"},
                "limit": {"type": "integer"},
            },
            "required": [],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Resolve brand nicknames/abbreviations and restaurant/menu nutrition on the public web "
            "when search_food misses or suggestWebSearch is true. Then call search_food with the "
            "full label name, or return provisional nutrition for user confirm."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
]


def run_tool(name: str, req: InterpretMealRequest, **kwargs: Any) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return {"error": "unknown_tool"}
    return handler(req, **kwargs)
