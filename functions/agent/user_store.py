"""Firestore source of truth: users/{uid} profile and diary entries."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from google.cloud.firestore_v1 import Client

from schemas import (
    DiaryDayEntry,
    DiaryDaySummary,
    DiaryEntry,
    DiaryContext,
    LongTermMemoryNote,
    MacroTotals,
    MealPlanSlot,
    PreferenceContext,
    normalize_firebase_payload,
)

logger = logging.getLogger("capy.user_store")

SCHEMA_VERSION = 1
DIARY_HISTORY_DAYS = 14

DEFAULT_TARGET = MacroTotals(calories=2000, proteinG=140, carbsG=200, fatG=65)


def get_db() -> Client:
    from firebase_admin import firestore

    # Named database from FIRESTORE_DATABASE_ID. Default id is `capy`, not `(default)`.
    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "capy").strip() or "capy"
    return firestore.client(database_id=database_id)


def _users(uid: str):
    return get_db().collection("users").document(uid)


def _days(uid: str):
    return _users(uid).collection("days")


def _entries(uid: str, day_key: str):
    return _days(uid).document(day_key).collection("entries")


def _day_keys(uid: str) -> list[str]:
    """Day ids under users/{uid}/days, including parents that only exist via entries."""
    return sorted(ref.id for ref in _days(uid).list_documents() if ref.id)


def _library(uid: str):
    return _users(uid).collection("library")


def _mutations(uid: str):
    return _users(uid).collection("clientMutations")


def default_profile_dict() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "timezone": "UTC",
        "dailyTarget": DEFAULT_TARGET.model_dump(),
        "mealPlan": [],
        "likes": [],
        "dislikes": [],
        "allergies": [],
        "diets": [],
        "assistanceLevel": "fullAssist",
        "responseStyle": "balanced",
        "voiceName": "Puck",
        "longTermMemory": [],
        "updatedAt": datetime.utcnow().isoformat() + "Z",
    }


def day_key_for_timezone(timezone: str, when: datetime | None = None) -> str:
    try:
        tz = ZoneInfo(timezone or "UTC")
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    instant = when or datetime.now(tz)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=tz)
    else:
        instant = instant.astimezone(tz)
    return instant.date().isoformat()


def previous_day_keys(anchor_day_key: str, count: int) -> list[str]:
    try:
        anchor = date.fromisoformat(anchor_day_key)
    except ValueError:
        return []
    return [(anchor - timedelta(days=offset)).isoformat() for offset in range(1, count + 1)]


def get_profile(uid: str) -> dict[str, Any]:
    snap = _users(uid).get()
    if not snap.exists:
        return default_profile_dict()
    data = snap.to_dict() or {}
    merged = normalize_firebase_payload({**default_profile_dict(), **data})
    if not isinstance(merged, dict):
        merged = default_profile_dict()
    merged.setdefault("schemaVersion", SCHEMA_VERSION)
    return merged


def patch_profile(uid: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "timezone",
        "dailyTarget",
        "mealPlan",
        "likes",
        "dislikes",
        "allergies",
        "diets",
        "assistanceLevel",
        "responseStyle",
        "voiceName",
        "longTermMemory",
    }
    normalized = normalize_firebase_payload(patch)
    if not isinstance(normalized, dict):
        normalized = {}
    updates = {k: v for k, v in normalized.items() if k in allowed and v is not None}
    if not updates:
        return get_profile(uid)
    updates["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    updates["schemaVersion"] = SCHEMA_VERSION
    ref = _users(uid)
    ref.set(updates, merge=True)
    return get_profile(uid)


def _macros_from_item(item: dict[str, Any]) -> MacroTotals:
    grams = float(item.get("grams") or 0)
    per = item.get("per100g") or {}
    if grams <= 0 or not per:
        return MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
    factor = grams / 100.0
    return MacroTotals(
        calories=float(per.get("calories") or 0) * factor,
        proteinG=float(per.get("proteinG") or 0) * factor,
        carbsG=float(per.get("carbsG") or 0) * factor,
        fatG=float(per.get("fatG") or 0) * factor,
    )


def _diary_entries_from_meal_doc(entry_id: str, data: dict[str, Any]) -> list[DiaryEntry]:
    meal_slot = data.get("mealSlot")
    rows: list[DiaryEntry] = []
    for index, item in enumerate(data.get("items") or []):
        if not isinstance(item, dict):
            continue
        per = item.get("per100g")
        per_model = MacroTotals.model_validate(per) if isinstance(per, dict) else None
        rows.append(
            DiaryEntry(
                name=str(item.get("name") or ""),
                mealSlot=meal_slot,
                grams=item.get("grams"),
                entryId=entry_id,
                itemIndex=index,
                foodId=item.get("foodId"),
                source=item.get("source"),
                per100g=per_model,
                ingredientFamily=item.get("ingredientFamily"),
            )
        )
    return rows


def _load_day_entries(uid: str, day_key: str) -> list[DiaryEntry]:
    rows: list[DiaryEntry] = []
    for snap in _entries(uid, day_key).stream():
        data = normalize_firebase_payload(snap.to_dict() or {})
        if not isinstance(data, dict):
            continue
        if data.get("deleted"):
            continue
        if not data.get("confirmed", True):
            continue
        rows.extend(_diary_entries_from_meal_doc(snap.id, data))
    return rows


def _sum_macros(entries: list[DiaryEntry]) -> MacroTotals:
    total = MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
    for entry in entries:
        if entry.grams is None or entry.per100g is None:
            continue
        part = _macros_from_item({"grams": entry.grams, "per100g": entry.per100g.model_dump()})
        total.calories += part.calories
        total.proteinG += part.proteinG
        total.carbsG += part.carbsG
        total.fatG += part.fatG
    return MacroTotals(
        calories=round(total.calories, 2),
        proteinG=round(total.proteinG, 2),
        carbsG=round(total.carbsG, 2),
        fatG=round(total.fatG, 2),
    )


def build_diary_context(uid: str, day_key: str, profile: dict[str, Any]) -> DiaryContext:
    target = MacroTotals.model_validate(profile.get("dailyTarget") or DEFAULT_TARGET.model_dump())
    today_rows = _load_day_entries(uid, day_key)
    eaten = _sum_macros(today_rows)
    remaining = MacroTotals(
        calories=max(target.calories - eaten.calories, 0),
        proteinG=max(target.proteinG - eaten.proteinG, 0),
        carbsG=max(target.carbsG - eaten.carbsG, 0),
        fatG=max(target.fatG - eaten.fatG, 0),
    )
    meal_plan = [
        MealPlanSlot.model_validate(slot)
        for slot in (profile.get("mealPlan") or [])
        if isinstance(slot, dict)
    ]
    previous: list[DiaryDaySummary] = []
    for key in previous_day_keys(day_key, DIARY_HISTORY_DAYS):
        day_rows = _load_day_entries(uid, key)
        if not day_rows:
            continue
        meal_ids = {row.entryId for row in day_rows if row.entryId}
        previous.append(
            DiaryDaySummary(
                dayKey=key,
                mealCount=len(meal_ids) or len(day_rows),
                itemNames=[row.name for row in day_rows],
                entries=[
                    DiaryDayEntry.model_validate(row.model_dump())
                    for row in day_rows
                ],
            )
        )
    return DiaryContext(
        today=today_rows,
        previousDays=previous,
        remaining=remaining,
        remainingSource="serverComputed",
        mealPlan=meal_plan,
    )


def preference_context_from_profile(profile: dict[str, Any]) -> PreferenceContext:
    return PreferenceContext(
        likes=list(profile.get("likes") or []),
        dislikes=list(profile.get("dislikes") or []),
        allergies=list(profile.get("allergies") or []),
        diets=list(profile.get("diets") or []),
    )


def long_term_from_profile(profile: dict[str, Any]) -> list[LongTermMemoryNote]:
    notes: list[LongTermMemoryNote] = []
    for raw in profile.get("longTermMemory") or []:
        if not isinstance(raw, dict):
            continue
        note_id = str(raw.get("id") or "").strip()
        text = str(raw.get("text") or "").strip()
        if note_id and text:
            notes.append(LongTermMemoryNote(id=note_id, text=text))
    return notes


def find_mutation(uid: str, client_mutation_id: str) -> Optional[dict[str, str]]:
    if not client_mutation_id:
        return None
    snap = _mutations(uid).document(client_mutation_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    day_key = data.get("dayKey")
    entry_id = data.get("entryId")
    if day_key and entry_id:
        return {"dayKey": str(day_key), "entryId": str(entry_id)}
    return None


def log_meal(
    uid: str,
    *,
    day_key: str,
    meal_slot: str,
    items: list[dict[str, Any]],
    entry_id: str | None = None,
    client_mutation_id: str | None = None,
    confirmed: bool = True,
) -> dict[str, str]:
    if client_mutation_id:
        existing = find_mutation(uid, client_mutation_id)
        if existing:
            return existing

    entry_id = (entry_id or "").strip() or str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    payload = {
        "entryId": entry_id,
        "dayKey": day_key,
        "mealSlot": meal_slot,
        "items": items,
        "confirmed": confirmed,
        "createdAt": now,
        "updatedAt": now,
    }
    if client_mutation_id:
        payload["clientMutationId"] = client_mutation_id

    _entries(uid, day_key).document(entry_id).set(payload, merge=True)
    if client_mutation_id:
        _mutations(uid).document(client_mutation_id).set(
            {"dayKey": day_key, "entryId": entry_id, "createdAt": now}
        )
    return {"dayKey": day_key, "entryId": entry_id}


def delete_entry(
    uid: str,
    *,
    day_key: str,
    entry_id: str,
    client_mutation_id: str | None = None,
) -> dict[str, str]:
    """Soft-delete a diary entry (hidden from diary context and harness pack)."""
    if client_mutation_id:
        existing = find_mutation(uid, client_mutation_id)
        if existing:
            return existing

    day_key = day_key.strip()
    entry_id = entry_id.strip()
    if not day_key or not entry_id:
        raise ValueError("dayKey and entryId are required")

    ref = _entries(uid, day_key).document(entry_id)
    snap = ref.get()
    if not snap.exists:
        raise LookupError("entry not found")

    now = datetime.utcnow().isoformat() + "Z"
    ref.set(
        {
            "deleted": True,
            "confirmed": False,
            "updatedAt": now,
        },
        merge=True,
    )
    if client_mutation_id:
        _mutations(uid).document(client_mutation_id).set(
            {"dayKey": day_key, "entryId": entry_id, "createdAt": now}
        )
    return {"dayKey": day_key, "entryId": entry_id}


_LIBRARY_KINDS = frozenset({"food", "recipe", "meal"})
_LIBRARY_ORIGINS = frozenset({"user", "aiGenerated"})


def find_library_mutation(uid: str, client_mutation_id: str) -> Optional[dict[str, str]]:
    if not client_mutation_id:
        return None
    snap = _mutations(uid).document(client_mutation_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    item_id = data.get("libraryItemId")
    if item_id:
        return {"id": str(item_id)}
    return None


def upsert_library_item(
    uid: str,
    *,
    item: dict[str, Any],
    client_mutation_id: str | None = None,
) -> dict[str, str]:
    """Create or replace users/{uid}/library/{id}."""
    if client_mutation_id:
        existing = find_library_mutation(uid, client_mutation_id)
        if existing:
            return existing

    item_id = str(item.get("id") or "").strip() or str(uuid.uuid4())
    name = str(item.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")

    kind = str(item.get("kind") or "food").strip()
    if kind not in _LIBRARY_KINDS:
        kind = "food"
    origin = str(item.get("origin") or "user").strip()
    if origin not in _LIBRARY_ORIGINS:
        origin = "user"

    ingredients = item.get("ingredients")
    if not isinstance(ingredients, list):
        ingredients = []

    now = datetime.utcnow().isoformat() + "Z"
    created = str(item.get("createdAt") or "").strip() or now
    payload = {
        "id": item_id,
        "name": name,
        "kind": kind,
        "origin": origin,
        "detail": str(item.get("detail") or "").strip(),
        "calories": float(item.get("calories") or 0),
        "proteinG": float(item.get("proteinG") or 0),
        "carbsG": float(item.get("carbsG") or 0),
        "fatG": float(item.get("fatG") or 0),
        "servingGrams": max(float(item.get("servingGrams") or 100), 1),
        "sourceFoodId": str(item.get("sourceFoodId") or "").strip(),
        "ingredients": ingredients,
        "deleted": False,
        "createdAt": created,
        "updatedAt": now,
    }
    if client_mutation_id:
        payload["clientMutationId"] = client_mutation_id

    _library(uid).document(item_id).set(payload, merge=True)
    if client_mutation_id:
        _mutations(uid).document(client_mutation_id).set(
            {"libraryItemId": item_id, "createdAt": now}
        )
    return {"id": item_id}


def delete_library_item(
    uid: str,
    *,
    item_id: str,
    client_mutation_id: str | None = None,
) -> dict[str, str]:
    """Soft-delete users/{uid}/library/{id}."""
    if client_mutation_id:
        existing = find_library_mutation(uid, client_mutation_id)
        if existing:
            return existing

    item_id = item_id.strip()
    if not item_id:
        raise ValueError("id is required")

    ref = _library(uid).document(item_id)
    now = datetime.utcnow().isoformat() + "Z"
    # Soft-delete even if missing so retries stay idempotent.
    ref.set(
        {
            "id": item_id,
            "deleted": True,
            "updatedAt": now,
        },
        merge=True,
    )
    if client_mutation_id:
        _mutations(uid).document(client_mutation_id).set(
            {"libraryItemId": item_id, "createdAt": now}
        )
    return {"id": item_id}


def list_diary_meals(uid: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
    """Meal docs under users/{uid}/days/{dayKey}/entries for client restore.

    Hidden rows (soft-deleted or unconfirmed) are omitted unless include_deleted.
    """
    rows: list[dict[str, Any]] = []
    for day_key in _day_keys(uid):
        for snap in _entries(uid, day_key).stream():
            data = normalize_firebase_payload(snap.to_dict() or {})
            if not isinstance(data, dict):
                continue
            deleted = bool(data.get("deleted"))
            confirmed = bool(data.get("confirmed", True))
            if not include_deleted and (deleted or not confirmed):
                continue
            items = data.get("items")
            data["entryId"] = str(data.get("entryId") or snap.id)
            data["dayKey"] = str(data.get("dayKey") or day_key)
            data["deleted"] = deleted
            data["confirmed"] = confirmed
            data["items"] = items if isinstance(items, list) else []
            rows.append(data)
    rows.sort(
        key=lambda row: (
            str(row.get("dayKey") or ""),
            str(row.get("createdAt") or ""),
            str(row.get("entryId") or ""),
        )
    )
    return rows


def list_library_items(uid: str, *, include_deleted: bool = False) -> list[dict[str, Any]]:
    """Return library docs (newest updated first)."""
    rows: list[dict[str, Any]] = []
    for snap in _library(uid).stream():
        data = snap.to_dict() or {}
        if not include_deleted and data.get("deleted"):
            continue
        data.setdefault("id", snap.id)
        rows.append(data)
    rows.sort(key=lambda row: str(row.get("updatedAt") or row.get("createdAt") or ""), reverse=True)
    return rows


def library_refs_for_interpret(uid: str, *, limit: int = 80) -> list[dict[str, Any]]:
    """Compact rows for harness libraryContext."""
    out: list[dict[str, Any]] = []
    for row in list_library_items(uid):
        out.append(
            {
                "id": str(row.get("id") or ""),
                "name": str(row.get("name") or ""),
                "kind": str(row.get("kind") or "food"),
                "calories": float(row.get("calories") or 0),
                "proteinG": float(row.get("proteinG") or 0),
                "carbsG": float(row.get("carbsG") or 0),
                "fatG": float(row.get("fatG") or 0),
                "servingGrams": max(float(row.get("servingGrams") or 100), 1),
            }
        )
        if len(out) >= limit:
            break
    return out
