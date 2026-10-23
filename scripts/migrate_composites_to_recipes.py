#!/usr/bin/env python3
"""Move seed composites from foodCorpus into recipes collection.

Reads foodCorpus docs with dataType == composite (seedRaw.components), writes
recipes/{recipeId}. Does not delete foodCorpus rows (safe rollback).

  python3 scripts/migrate_composites_to_recipes.py --project your-gcp-project
  python3 scripts/migrate_composites_to_recipes.py --project your-gcp-project --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "functions"))


def _init_firebase(project: str | None) -> None:
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return
    options = {"projectId": project} if project else None
    firebase_admin.initialize_app(credentials.ApplicationDefault(), options)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate foodCorpus composites → recipes")
    parser.add_argument("--project", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    from agent.tools.search.recipes_store import (
        list_composite_corpus_docs,
        recipe_from_composite_seed_raw,
        upsert_recipes,
        write_catalog_meta,
    )
    from agent.user_store import get_db

    _init_firebase(args.project)
    db = get_db()

    corpus_rows = list_composite_corpus_docs(db)
    if not corpus_rows:
        logging.warning("no composite docs found in foodCorpus")
        return 0

    recipes: list[dict] = []
    for row in corpus_rows:
        recipe_id = str(row.get("foodId") or "").strip()
        seed_raw = row.get("seedRaw")
        if not recipe_id or not isinstance(seed_raw, dict):
            logging.warning("skip invalid composite row: %s", recipe_id or row)
            continue
        doc = recipe_from_composite_seed_raw(
            recipe_id,
            seed_raw,
            catalog_version=row.get("catalogVersion"),
        )
        if doc:
            recipes.append(doc)
            logging.info("prepared recipe %s (%s ingredients)", recipe_id, len(doc["ingredients"]))

    if not recipes:
        logging.error("no recipes built from corpus")
        return 1

    if args.dry_run:
        logging.info("dry-run: would write %s recipes", len(recipes))
        return 0

    written = upsert_recipes(db, recipes)
    write_catalog_meta(
        db,
        recipe_count=written,
        extra={"migratedFrom": "foodCorpus", "migration": "composites_v1"},
    )
    logging.info("wrote %s recipes to recipes/ (foodCorpus composites left in place)", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
