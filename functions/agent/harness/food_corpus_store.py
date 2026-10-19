"""Firestore corpus for USDA FDC search API responses.

Collections (top-level, Admin SDK only — same pattern as users / agentGraphCheckpoints):
  foodCorpus/{foodId}     — atomic foods, FDC write-through, seed staples, templates
  fdcSearchSlices/{id}    — ordered foodId list for (query, slice, pageSize)
  recipes/{recipeId}      — multi-ingredient dishes (see recipes_store.py); not foodCorpus
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger("capy.food_corpus_store")

FOOD_CORPUS_COLLECTION = "foodCorpus"
FDC_SEARCH_SLICES_COLLECTION = "fdcSearchSlices"

_SLICE_BRANDED = "branded"
_SLICE_FOUNDATION_SR = "foundation_sr"
_SLICE_SURVEY = "survey_fndds"

_MEMORY_FOODS: dict[str, dict[str, Any]] = {}
_MEMORY_SLICES: dict[str, dict[str, Any]] = {}


def slice_key_for_data_types(data_types: list[str]) -> str:
    normalized = tuple(sorted(data_types))
    if normalized == ("Branded",):
        return _SLICE_BRANDED
    if normalized == ("Foundation", "SR Legacy"):
        return _SLICE_FOUNDATION_SR
    if normalized == ("Survey (FNDDS)",):
        return _SLICE_SURVEY
    return "|".join(sorted(data_types))


def corpus_store_enabled() -> bool:
    raw = os.environ.get("USDA_FDC_CACHE", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def corpus_ttl_seconds() -> Optional[float]:
    raw = os.environ.get("USDA_FDC_CACHE_TTL_SECONDS", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _use_memory_store() -> bool:
    return os.environ.get("USDA_FDC_STORE", "").strip().lower() == "memory"


def reset_memory_store() -> None:
    _MEMORY_FOODS.clear()
    _MEMORY_SLICES.clear()


def _query_norm(query: str) -> str:
    return query.strip().casefold()


def food_id_for_fdc(fdc_id: int | str) -> str:
    return f"usda_{int(fdc_id)}"


def _slice_document_id(query_norm: str, slice_key: str, page_size: int) -> str:
    key = f"{query_norm}\0{slice_key}\0{page_size}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _now_epoch() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _slice_expired(updated_at_epoch: float) -> bool:
    ttl = corpus_ttl_seconds()
    if ttl is None:
        return False
    return (_now_epoch() - updated_at_epoch) > ttl


def _food_document(food: dict[str, Any], *, now_epoch: float) -> Optional[tuple[str, dict[str, Any]]]:
    fdc_id = food.get("fdcId")
    if fdc_id is None:
        return None
    try:
        fdc_int = int(fdc_id)
    except (TypeError, ValueError):
        return None
    food_id = food_id_for_fdc(fdc_int)
    data_type = str(food.get("dataType") or "")
    return food_id, {
        "foodId": food_id,
        "fdcId": fdc_int,
        "source": "fdc_search",
        "dataType": data_type,
        "fdcRaw": food,
        "updatedAt": _now_iso(),
        "updatedAtEpoch": now_epoch,
    }


def _get_db():
    from agent.user_store import get_db

    return get_db()


def put_search_slice(
    query: str,
    slice_key: str,
    page_size: int,
    foods: list[dict[str, Any]],
) -> None:
    now_epoch = _now_epoch()
    query_norm = _query_norm(query)
    slice_id = _slice_document_id(query_norm, slice_key, page_size)
    food_ids: list[str] = []

    food_docs: list[tuple[str, dict[str, Any]]] = []
    for food in foods:
        row = _food_document(food, now_epoch=now_epoch)
        if row is None:
            continue
        doc_id, payload = row
        food_docs.append((doc_id, payload))
        food_ids.append(doc_id)

    slice_payload = {
        "queryNorm": query_norm,
        "sliceKey": slice_key,
        "pageSize": page_size,
        "foodIds": food_ids,
        "updatedAt": _now_iso(),
        "updatedAtEpoch": now_epoch,
    }

    if _use_memory_store():
        for doc_id, payload in food_docs:
            _MEMORY_FOODS[doc_id] = payload
        _MEMORY_SLICES[slice_id] = slice_payload
        return

    try:
        db = _get_db()
        batch = db.batch()
        count = 0
        for doc_id, payload in food_docs:
            batch.set(db.collection(FOOD_CORPUS_COLLECTION).document(doc_id), payload, merge=True)
            count += 1
            if count >= 450:
                batch.commit()
                batch = db.batch()
                count = 0
        batch.set(
            db.collection(FDC_SEARCH_SLICES_COLLECTION).document(slice_id),
            slice_payload,
            merge=True,
        )
        batch.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fdc corpus write-through failed: %s", exc)


def get_search_slice(
    query: str,
    slice_key: str,
    page_size: int,
) -> Optional[list[dict[str, Any]]]:
    query_norm = _query_norm(query)
    slice_id = _slice_document_id(query_norm, slice_key, page_size)

    if _use_memory_store():
        slice_doc = _MEMORY_SLICES.get(slice_id)
        if slice_doc is None:
            return None
        if _slice_expired(float(slice_doc.get("updatedAtEpoch") or 0)):
            return None
        food_ids = slice_doc.get("foodIds") or []
        if not isinstance(food_ids, list):
            return None
        foods: list[dict[str, Any]] = []
        for food_id in food_ids:
            food_doc = _MEMORY_FOODS.get(str(food_id))
            if food_doc is None:
                return None
            raw = food_doc.get("fdcRaw")
            if not isinstance(raw, dict):
                return None
            foods.append(raw)
        return foods

    try:
        db = _get_db()
        slice_snap = db.collection(FDC_SEARCH_SLICES_COLLECTION).document(slice_id).get()
        if not slice_snap.exists:
            return None
        slice_data = slice_snap.to_dict() or {}
        if _slice_expired(float(slice_data.get("updatedAtEpoch") or 0)):
            return None
        food_ids = slice_data.get("foodIds") or []
        if not isinstance(food_ids, list):
            return None
        if not food_ids:
            return []

        refs = [db.collection(FOOD_CORPUS_COLLECTION).document(str(fid)) for fid in food_ids]
        snaps = db.get_all(refs)
        by_id: dict[str, dict[str, Any]] = {}
        for snap in snaps:
            if not snap.exists:
                continue
            data = snap.to_dict() or {}
            fid = str(data.get("foodId") or snap.id)
            by_id[fid] = data

        foods: list[dict[str, Any]] = []
        for food_id in food_ids:
            food_doc = by_id.get(str(food_id))
            if food_doc is None:
                return None
            raw = food_doc.get("fdcRaw")
            if not isinstance(raw, dict):
                return None
            foods.append(raw)
        return foods
    except Exception as exc:  # noqa: BLE001
        logger.warning("fdc corpus read failed: %s", exc)
        return None
