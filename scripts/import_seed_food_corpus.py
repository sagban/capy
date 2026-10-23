#!/usr/bin/env python3
"""Upload functions/seed/SeedFoods.json into Firestore foodCorpus.

Requires Application Default Credentials and Firebase Admin (same project as Functions).

  cd /path/to/capy
  python3 scripts/import_seed_food_corpus.py --dry-run
  python3 scripts/import_seed_food_corpus.py --project your-gcp-project
  python3 scripts/import_seed_food_corpus.py --force

Meta: foodCorpus/_meta/catalog/current
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = ROOT / "functions"
DEFAULT_SEED = FUNCTIONS / "seed" / "SeedFoods.json"

sys.path.insert(0, str(FUNCTIONS))


def _init_firebase(project: str | None) -> None:
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return
    options = {"projectId": project} if project else None
    firebase_admin.initialize_app(credentials.ApplicationDefault(), options)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import SeedFoods.json into foodCorpus")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_SEED,
        help=f"Seed JSON path (default: {DEFAULT_SEED})",
    )
    parser.add_argument("--project", type=str, default=None, help="GCP/Firebase project id")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report counts only")
    parser.add_argument("--force", action="store_true", help="Import even if file hash unchanged")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    path = args.input.resolve()
    if not path.is_file():
        logging.error("seed file not found: %s", path)
        return 1

    seed = json.loads(path.read_text(encoding="utf-8"))
    from agent.tools.search.seed_corpus_import import file_sha256, import_seed_catalog
    from agent.user_store import get_db

    file_hash = file_sha256(path)
    _init_firebase(args.project)
    db = get_db()

    result = import_seed_catalog(
        seed,
        db=db,
        file_hash=file_hash,
        dry_run=args.dry_run,
        force=args.force,
    )
    logging.info("result: %s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
