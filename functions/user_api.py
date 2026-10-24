"""Callable write APIs for user profile and diary."""

from __future__ import annotations

import logging
from typing import Any

from firebase_functions import https_fn
from pydantic import ValidationError

from agent.auth import resolve_callable_uid
from agent.thread_store import (
    append_assistant_turn,
    clamp_page_limit,
    get_thread_view,
    normalize_thread_id,
    note_day_rollover,
    reset_thread,
)
from agent.tools.search.open_food_facts import lookup_barcode as off_lookup_barcode
from agent.tools.search.open_food_facts import normalize_gtin
from agent.user_store import delete_entry as store_delete_entry
from agent.user_store import delete_library_item as store_delete_library_item
from agent.user_store import list_diary_meals as store_list_diary_meals
from agent.user_store import list_library_items as store_list_library_items
from agent.user_store import log_meal as store_log_meal
from agent.user_store import patch_profile as store_patch_profile
from agent.user_store import upsert_library_item as store_upsert_library_item
from schemas import MacroTotals, normalize_firebase_payload

logger = logging.getLogger("capy.user_api")


def _uid(req: https_fn.CallableRequest) -> str:
    return resolve_callable_uid(req)


def _validate_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="items must be a non-empty list.",
        )
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Each item must be an object.",
            )
        name = str(item.get("name") or "").strip()
        if not name:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Each item needs a name.",
            )
        grams = item.get("grams")
        if grams is None or float(grams) <= 0:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Each item needs grams.",
            )
        per = item.get("per100g")
        if not isinstance(per, dict):
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Each item needs per100g.",
            )
        try:
            MacroTotals.model_validate(per)
        except ValidationError as exc:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Each item needs per100g with calories, proteinG, carbsG, and fatG.",
            ) from exc
        out.append(item)
    return out


def patch_profile_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_firebase_payload(raw)
    if not isinstance(normalized, dict):
        normalized = {}
    patch = {k: v for k, v in normalized.items() if k != "useServerContext"}
    profile = store_patch_profile(uid, patch)
    logger.info("patch_profile uid=%s keys=%s", uid, sorted(patch.keys()))
    return {"profile": profile}


def handle_patch_profile(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return patch_profile_for_uid(uid, raw)


def log_meal_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    day_key = str(raw.get("dayKey") or "").strip()
    meal_slot = str(raw.get("mealSlot") or "").strip()
    if not day_key or not meal_slot:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="dayKey and mealSlot are required.",
        )
    normalized = normalize_firebase_payload(raw)
    if not isinstance(normalized, dict):
        normalized = {}
    items = _validate_items(normalized.get("items"))
    result = store_log_meal(
        uid,
        day_key=day_key,
        meal_slot=meal_slot,
        items=items,
        entry_id=str(raw.get("entryId") or "").strip() or None,
        client_mutation_id=str(raw.get("clientMutationId") or "").strip() or None,
        confirmed=bool(raw.get("confirmed", True)),
    )
    logger.info("log_meal uid=%s day=%s entry=%s", uid, result["dayKey"], result["entryId"])
    return result


def handle_log_meal(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return log_meal_for_uid(uid, raw)


def delete_meal_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    day_key = str(raw.get("dayKey") or "").strip()
    entry_id = str(raw.get("entryId") or "").strip()
    if not day_key or not entry_id:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="dayKey and entryId are required.",
        )
    try:
        result = store_delete_entry(
            uid,
            day_key=day_key,
            entry_id=entry_id,
            client_mutation_id=str(raw.get("clientMutationId") or "").strip() or None,
        )
    except LookupError:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.NOT_FOUND,
            message="That meal entry was not found.",
        ) from None
    logger.info("delete_meal uid=%s day=%s entry=%s", uid, result["dayKey"], result["entryId"])
    return result


def handle_delete_meal(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return delete_meal_for_uid(uid, raw)


def get_thread_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    thread_id = normalize_thread_id(raw.get("threadId"))
    limit = clamp_page_limit(raw.get("limit"))
    cursor = str(raw.get("cursor") or "").strip() or None
    return get_thread_view(uid, thread_id, limit=limit, cursor=cursor)


def handle_get_thread(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return get_thread_for_uid(uid, raw)


def patch_thread_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    thread_id = normalize_thread_id(raw.get("threadId"))
    if raw.get("reset") is True:
        logger.info("patch_thread reset uid=%s thread=%s", uid, thread_id)
        return reset_thread(uid, thread_id)
    conversation = None
    rollover = raw.get("dayRollover")
    if isinstance(rollover, dict):
        previous = str(rollover.get("previousDayKey") or "").strip()
        if previous:
            count = int(rollover.get("mealCount") or 0)
            conversation = note_day_rollover(uid, thread_id, previous, count)
    assistant_text = str(raw.get("assistantText") or "").strip()
    if assistant_text:
        conversation = append_assistant_turn(
            uid,
            thread_id,
            assistant_text,
            clear_working_memory=bool(raw.get("clearWorkingMemory")),
        )
    if conversation is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="assistantText, dayRollover, or reset is required.",
        )
    return conversation


def handle_patch_thread(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return patch_thread_for_uid(uid, raw)


def lookup_barcode_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    gtin = normalize_gtin(str(raw.get("gtin") or ""))
    if len(gtin) < 8:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="gtin must be at least 8 digits.",
        )
    result = off_lookup_barcode(gtin)
    logger.info(
        "lookup_barcode uid=%s gtin=%s found=%s",
        uid,
        gtin,
        bool(result.get("found")),
    )
    return result


def handle_lookup_barcode(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return lookup_barcode_for_uid(uid, raw)


def upsert_library_item_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    item = raw.get("item")
    if not isinstance(item, dict):
        # Allow flat payload (item fields at top level) for simpler clients.
        item = {k: v for k, v in raw.items() if k not in {"clientMutationId", "useServerContext"}}
    if not isinstance(item, dict) or not item:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="item is required.",
        )
    try:
        result = store_upsert_library_item(
            uid,
            item=item,
            client_mutation_id=str(raw.get("clientMutationId") or "").strip() or None,
        )
    except ValueError as exc:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message=str(exc),
        ) from exc
    logger.info("upsert_library_item uid=%s id=%s", uid, result["id"])
    return result


def handle_upsert_library_item(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return upsert_library_item_for_uid(uid, raw)


def delete_library_item_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    item_id = str(raw.get("id") or "").strip()
    if not item_id:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="id is required.",
        )
    try:
        result = store_delete_library_item(
            uid,
            item_id=item_id,
            client_mutation_id=str(raw.get("clientMutationId") or "").strip() or None,
        )
    except ValueError as exc:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message=str(exc),
        ) from exc
    logger.info("delete_library_item uid=%s id=%s", uid, result["id"])
    return result


def handle_delete_library_item(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return delete_library_item_for_uid(uid, raw)


def list_diary_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    include_deleted = bool(raw.get("includeDeleted"))
    meals = store_list_diary_meals(uid, include_deleted=include_deleted)
    logger.info("list_diary uid=%s meals=%s include_deleted=%s", uid, len(meals), include_deleted)
    return {"meals": meals}


def handle_list_diary(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return list_diary_for_uid(uid, raw)


def list_library_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    include_deleted = bool(raw.get("includeDeleted"))
    items = store_list_library_items(uid, include_deleted=include_deleted)
    return {"items": items}


def handle_list_library(req: https_fn.CallableRequest) -> dict[str, Any]:
    uid = _uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    return list_library_for_uid(uid, raw)
