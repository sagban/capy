"""Firestore recipes: named dishes built from foodCorpus ingredient references.

Collection: recipes/{recipeId} on database FIRESTORE_DATABASE_ID (default capy).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Literal, Optional

logger = logging.getLogger("capy.recipes_store")

RECIPES_COLLECTION = "recipes"
META_DOC_ID = "_meta"
CATALOG_META_SUBCOLLECTION = "catalog"
CATALOG_META_DOC_ID = "current"

RecipeKind = Literal["composite", "recipe"]

_BATCH_LIMIT = 450


def _now_epoch() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _get_db():
    from agent.user_store import get_db

    return get_db()


def _meta_ref(db):
    return (
        db.collection(RECIPES_COLLECTION)
        .document(META_DOC_ID)
        .collection(CATALOG_META_SUBCOLLECTION)
        .document(CATALOG_META_DOC_ID)
    )


def normalize_ingredients(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        food_id = str(row.get("foodId") or "").strip()
        if not food_id:
            continue
        try:
            grams = float(row.get("grams") or 0)
        except (TypeError, ValueError):
            continue
        if grams <= 0:
            continue
        out.append({"foodId": food_id, "grams": grams})
    return out


def build_recipe_document(
    *,
    recipe_id: str,
    name: str,
    ingredients: list[dict[str, Any]],
    kind: RecipeKind = "recipe",
    notes: str = "",
    source: str = "seed",
    catalog_version: Optional[int] = None,
    now_epoch: Optional[float] = None,
) -> dict[str, Any]:
    epoch = now_epoch if now_epoch is not None else _now_epoch()
    return {
        "recipeId": recipe_id,
        "name": name,
        "notes": notes,
        "kind": kind,
        "ingredients": ingredients,
        "source": source,
        "catalogVersion": catalog_version,
        "updatedAt": _now_iso(),
        "updatedAtEpoch": epoch,
    }


def recipe_from_composite_seed_raw(
    composite_id: str,
    seed_raw: dict[str, Any],
    *,
    catalog_version: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    components = normalize_ingredients(list(seed_raw.get("components") or []))
    if not components:
        return None
    name = str(seed_raw.get("name") or composite_id)
    return build_recipe_document(
        recipe_id=composite_id,
        name=name,
        ingredients=components,
        kind="composite",
        notes="",
        source="seed",
        catalog_version=catalog_version,
    )


def upsert_recipes(
    db,
    recipes: list[dict[str, Any]],
) -> int:
    if not recipes:
        return 0
    batch = db.batch()
    coll = db.collection(RECIPES_COLLECTION)
    ops = 0
    written = 0
    for payload in recipes:
        recipe_id = str(payload.get("recipeId") or "").strip()
        if not recipe_id:
            continue
        batch.set(coll.document(recipe_id), payload, merge=True)
        ops += 1
        written += 1
        if ops >= _BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            ops = 0
    if ops:
        batch.commit()
    return written


def write_catalog_meta(
    db,
    *,
    recipe_count: int,
    file_hash: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    body: dict[str, Any] = {
        "recipeCount": recipe_count,
        "importedAt": _now_iso(),
        "importedAtEpoch": _now_epoch(),
    }
    if file_hash:
        body["fileHash"] = file_hash
    if extra:
        body.update(extra)
    _meta_ref(db).set(body, merge=True)


def list_composite_corpus_docs(db) -> list[dict[str, Any]]:
    """foodCorpus rows migrated from seed composites (dataType composite)."""
    try:
        query = db.collection("foodCorpus").where("dataType", "==", "composite")
        return [snap.to_dict() or {} for snap in query.stream()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("list composite corpus docs failed: %s", exc)
        return []
