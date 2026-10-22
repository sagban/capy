"""Seed corpus Firestore document builders."""

from __future__ import annotations

import json
from pathlib import Path

from agent.tools.search.seed_corpus_import import (
    data_type_for_food,
    file_sha256,
    iter_recipes_from_seed,
    iter_seed_documents,
)

_SEED = Path(__file__).resolve().parents[1] / "seed" / "SeedFoods.json"


def test_data_type_mapping():
    assert data_type_for_food({"source": "usda_sr_legacy"}) == "SR Legacy"
    assert data_type_for_food({"source": "usda_foundation"}) == "Foundation"
    assert data_type_for_food({"source": "overlay"}) == "overlay"


def test_iter_seed_documents_counts():
    seed = json.loads(_SEED.read_text(encoding="utf-8"))
    docs = iter_seed_documents(seed)
    assert len(docs) == len(seed["foods"]) + len(seed["templates"])
    recipes = iter_recipes_from_seed(seed)
    assert len(recipes) == len(seed["composites"])
    assert recipes[0]["kind"] == "composite"
    assert recipes[0]["ingredients"]
    by_id = {doc_id: payload for doc_id, payload in docs}
    tpl = by_id["tpl_dal_roti"]
    assert tpl["dataType"] == "template"


def test_file_hash_stable():
    h1 = file_sha256(_SEED)
    h2 = file_sha256(_SEED)
    assert h1 == h2
    assert len(h1) == 64
