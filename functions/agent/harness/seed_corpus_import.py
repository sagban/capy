"""Import SeedFoods.json into Firestore foodCorpus (one-off / repeatable)."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from agent.harness.food_corpus_store import FOOD_CORPUS_COLLECTION
from schemas import MacroTotals

logger = logging.getLogger("capy.seed_corpus_import")

META_DOC_ID = "_meta"
CATALOG_META_SUBCOLLECTION = "catalog"
CATALOG_META_DOC_ID = "current"

_BATCH_LIMIT = 450

_JSON_SOURCE_TO_DATA_TYPE = {
    "usda_sr_legacy": "SR Legacy",
    "usda_foundation": "Foundation",
    "overlay": "overlay",
}


def _now_epoch() -> float:
    return time.time()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_type_for_food(row: dict[str, Any]) -> str:
    raw = str(row.get("source") or "").strip()
    return _JSON_SOURCE_TO_DATA_TYPE.get(raw, raw or "unknown")


def _macros_from_food_row(row: dict[str, Any]) -> MacroTotals:
    per = row.get("per100g") or {}
    return MacroTotals(
        calories=float(per.get("calories") or 0),
        proteinG=float(per.get("proteinG") or 0),
        carbsG=float(per.get("carbsG") or 0),
        fatG=float(per.get("fatG") or 0),
    )


def composite_per100g(
    composite: dict[str, Any],
    foods_by_id: dict[str, dict[str, Any]],
) -> dict[str, float]:
    totals = MacroTotals(calories=0, proteinG=0, carbsG=0, fatG=0)
    grams_total = 0.0
    for component in composite.get("components") or []:
        if not isinstance(component, dict):
            continue
        base = foods_by_id.get(str(component.get("foodId") or ""))
        if not base:
            continue
        macros = _macros_from_food_row(base)
        grams = float(component.get("grams") or 0)
        factor = grams / 100.0
        totals = MacroTotals(
            calories=totals.calories + macros.calories * factor,
            proteinG=totals.proteinG + macros.proteinG * factor,
            carbsG=totals.carbsG + macros.carbsG * factor,
            fatG=totals.fatG + macros.fatG * factor,
        )
        grams_total += grams
    if grams_total > 0:
        scale = 100.0 / grams_total
        return {
            "calories": totals.calories * scale,
            "proteinG": totals.proteinG * scale,
            "carbsG": totals.carbsG * scale,
            "fatG": totals.fatG * scale,
        }
    return {"calories": 0.0, "proteinG": 0.0, "carbsG": 0.0, "fatG": 0.0}


def build_seed_document(
    *,
    food_id: str,
    data_type: str,
    seed_raw: dict[str, Any],
    display_name: str,
    family: str,
    aliases: list[str],
    catalog_version: int,
    now_epoch: float,
) -> dict[str, Any]:
    return {
        "foodId": food_id,
        "source": "seed",
        "dataType": data_type,
        "seedRaw": seed_raw,
        "displayName": display_name,
        "family": family,
        "aliases": aliases,
        "catalogVersion": catalog_version,
        "updatedAt": _now_iso(),
        "updatedAtEpoch": now_epoch,
    }


def iter_seed_documents(seed: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    catalog_version = int(seed.get("version") or 0)
    now_epoch = _now_epoch()
    foods = [f for f in seed.get("foods") or [] if isinstance(f, dict)]
    foods_by_id = {str(f["id"]): f for f in foods if f.get("id")}

    out: list[tuple[str, dict[str, Any]]] = []
    for food in foods:
        food_id = str(food["id"])
        aliases = [str(a) for a in (food.get("aliases") or []) if str(a).strip()]
        doc = build_seed_document(
            food_id=food_id,
            data_type=data_type_for_food(food),
            seed_raw=food,
            display_name=str(food.get("name") or ""),
            family=str(food.get("family") or ""),
            aliases=aliases,
            catalog_version=catalog_version,
            now_epoch=now_epoch,
        )
        out.append((food_id, doc))

    for template in seed.get("templates") or []:
        if not isinstance(template, dict) or not template.get("id"):
            continue
        food_id = str(template["id"])
        doc = build_seed_document(
            food_id=food_id,
            data_type="template",
            seed_raw=template,
            display_name=str(template.get("name") or ""),
            family="template",
            aliases=[],
            catalog_version=catalog_version,
            now_epoch=now_epoch,
        )
        out.append((food_id, doc))

    return out


def iter_recipes_from_seed(seed: dict[str, Any]) -> list[dict[str, Any]]:
    from agent.harness.recipes_store import recipe_from_composite_seed_raw

    catalog_version = int(seed.get("version") or 0)
    recipes: list[dict[str, Any]] = []
    for composite in seed.get("composites") or []:
        if not isinstance(composite, dict) or not composite.get("id"):
            continue
        recipe_id = str(composite["id"])
        doc = recipe_from_composite_seed_raw(
            recipe_id,
            composite,
            catalog_version=catalog_version,
        )
        if doc:
            recipes.append(doc)
    return recipes


def _meta_ref(db):
    return (
        db.collection(FOOD_CORPUS_COLLECTION)
        .document(META_DOC_ID)
        .collection(CATALOG_META_SUBCOLLECTION)
        .document(CATALOG_META_DOC_ID)
    )


def read_catalog_meta(db) -> Optional[dict[str, Any]]:
    snap = _meta_ref(db).get()
    if not snap.exists:
        return None
    return snap.to_dict()


def write_catalog_meta(
    db,
    *,
    version: int,
    food_count: int,
    file_hash: str,
    counts: dict[str, int],
) -> None:
    _meta_ref(db).set(
        {
            "version": version,
            "importedAt": _now_iso(),
            "importedAtEpoch": _now_epoch(),
            "foodCount": food_count,
            "fileHash": file_hash,
            "counts": counts,
        },
        merge=True,
    )


def write_seed_documents(
    db,
    documents: list[tuple[str, dict[str, Any]]],
) -> int:
    written = 0
    batch = db.batch()
    ops = 0
    coll = db.collection(FOOD_CORPUS_COLLECTION)
    for food_id, payload in documents:
        batch.set(coll.document(food_id), payload, merge=True)
        ops += 1
        written += 1
        if ops >= _BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            ops = 0
    if ops:
        batch.commit()
    return written


def import_seed_catalog(
    seed: dict[str, Any],
    *,
    db,
    file_hash: str,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    version = int(seed.get("version") or 0)
    documents = iter_seed_documents(seed)
    counts = {
        "foods": len(seed.get("foods") or []),
        "composites": len(seed.get("composites") or []),
        "templates": len(seed.get("templates") or []),
    }
    total = len(documents)

    if not force:
        existing = read_catalog_meta(db)
        if existing and str(existing.get("fileHash") or "") == file_hash:
            logger.info("seed corpus unchanged (hash match); skipping import")
            return {
                "skipped": True,
                "reason": "hash_unchanged",
                "foodCount": int(existing.get("foodCount") or 0),
                "fileHash": file_hash,
            }

    if dry_run:
        return {
            "skipped": False,
            "dryRun": True,
            "version": version,
            "foodCount": total,
            "counts": counts,
            "fileHash": file_hash,
        }

    written = write_seed_documents(db, documents)
    from agent.harness.recipes_store import upsert_recipes, write_catalog_meta as write_recipes_meta

    recipe_docs = iter_recipes_from_seed(seed)
    recipes_written = upsert_recipes(db, recipe_docs)
    if recipes_written:
        write_recipes_meta(
            db,
            recipe_count=recipes_written,
            file_hash=file_hash,
            extra={"source": "seed_import"},
        )
    write_catalog_meta(
        db,
        version=version,
        food_count=written,
        file_hash=file_hash,
        counts=counts,
    )
    return {
        "skipped": False,
        "dryRun": False,
        "version": version,
        "foodCount": written,
        "recipeCount": recipes_written,
        "counts": counts,
        "fileHash": file_hash,
    }
