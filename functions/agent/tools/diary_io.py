"""Diary read and write. Callers pass every field. uid is bound by the edge, not the model."""

from __future__ import annotations

from typing import Any

from firebase_functions import https_fn

from agent.user_store import build_diary_context, get_profile
from user_api import delete_meal_for_uid, log_meal_for_uid


def _entry(row: Any) -> dict[str, Any]:
    per = getattr(row, "per100g", None)
    return {
        "entryId": getattr(row, "entryId", None),
        "itemIndex": getattr(row, "itemIndex", None),
        "name": getattr(row, "name", None),
        "grams": getattr(row, "grams", None),
        "mealSlot": getattr(row, "mealSlot", None),
        "foodId": getattr(row, "foodId", None),
        "source": getattr(row, "source", None),
        "per100g": per.model_dump(mode="json") if per is not None and hasattr(per, "model_dump") else per,
        "ingredientFamily": getattr(row, "ingredientFamily", None),
    }


def get_diary(day_key: str, entries: list[Any], remaining: dict[str, Any]) -> dict[str, Any]:
    dumped: list[dict[str, Any]] = []
    for row in entries or []:
        if isinstance(row, dict):
            dumped.append(
                {
                    "entryId": row.get("entryId"),
                    "itemIndex": row.get("itemIndex"),
                    "name": row.get("name"),
                    "grams": row.get("grams"),
                    "mealSlot": row.get("mealSlot"),
                    "foodId": row.get("foodId"),
                    "source": row.get("source"),
                    "per100g": row.get("per100g"),
                    "ingredientFamily": row.get("ingredientFamily"),
                }
            )
        else:
            dumped.append(_entry(row))
    return {"dayKey": day_key, "entries": dumped, "remaining": remaining}


def get_diary_for_uid(uid: str, day_key: str) -> dict[str, Any]:
    profile = get_profile(uid)
    ctx = build_diary_context(uid, day_key, profile)
    return get_diary(day_key, list(ctx.today or []), ctx.remaining.model_dump(mode="json"))


def write_food_entry(
    uid: str,
    day_key: str,
    meal_slot: str,
    kind: str,
    name: str,
    grams: float,
    per100g: dict[str, Any],
    foodId: str | None = None,
    source: str | None = None,
    ingredientFamily: str | None = None,
    citationUrl: str | None = None,
    entry_id: str | None = None,
    client_mutation_id: str | None = None,
    confirmed: bool = True,
) -> dict[str, Any]:
    """Write one diary entry. kind is food, recipe, or meal."""
    item: dict[str, Any] = {
        "name": name,
        "grams": grams,
        "per100g": per100g,
        "kind": kind,
    }
    if foodId:
        item["foodId"] = foodId
    if source:
        item["source"] = source
    if ingredientFamily:
        item["ingredientFamily"] = ingredientFamily
    if citationUrl:
        item["citationUrl"] = citationUrl
    return log_meal(
        uid,
        day_key,
        meal_slot,
        [item],
        entry_id=entry_id,
        client_mutation_id=client_mutation_id,
        confirmed=confirmed,
    )


def log_meal(
    uid: str,
    day_key: str,
    meal_slot: str,
    items: list[dict[str, Any]],
    entry_id: str | None = None,
    client_mutation_id: str | None = None,
    confirmed: bool = True,
) -> dict[str, Any]:
    cleaned = [{key: value for key, value in item.items() if value is not None} for item in items]
    payload: dict[str, Any] = {
        "dayKey": day_key,
        "mealSlot": meal_slot,
        "items": cleaned,
        "confirmed": confirmed,
    }
    if entry_id:
        payload["entryId"] = entry_id
    if client_mutation_id:
        payload["clientMutationId"] = client_mutation_id
    try:
        written = log_meal_for_uid(uid, payload)
    except https_fn.HttpsError as exc:
        return {"error": "bad_args", "message": exc.message}
    return {"entryId": written.get("entryId"), "dayKey": written.get("dayKey")}


def delete_meal(
    uid: str,
    day_key: str,
    entry_id: str,
    client_mutation_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"dayKey": day_key, "entryId": entry_id}
    if client_mutation_id:
        payload["clientMutationId"] = client_mutation_id
    try:
        written = delete_meal_for_uid(uid, payload)
    except https_fn.HttpsError as exc:
        return {"error": "bad_args", "message": exc.message}
    return {"entryId": written.get("entryId"), "dayKey": written.get("dayKey")}
