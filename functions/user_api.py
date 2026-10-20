"""Callable write APIs for user profile and diary."""

from __future__ import annotations

import logging
from typing import Any

from firebase_functions import https_fn

from agent.auth import resolve_callable_uid
from agent.thread_store import (
    append_assistant_turn,
    clamp_page_limit,
    get_thread_view,
    normalize_thread_id,
    note_day_rollover,
)
from agent.harness.search.open_food_facts import lookup_barcode as off_lookup_barcode
from agent.harness.search.open_food_facts import normalize_gtin
from agent.user_store import delete_entry as store_delete_entry
from agent.user_store import log_meal as store_log_meal
from agent.user_store import patch_profile as store_patch_profile
from schemas import MacroTotals

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
        if isinstance(per, dict):
            MacroTotals.model_validate(per)
        out.append(item)
    return out


def patch_profile_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    patch = {k: v for k, v in raw.items() if k != "useServerContext"}
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
    items = _validate_items(raw.get("items"))
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
            message="assistantText or dayRollover is required.",
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
