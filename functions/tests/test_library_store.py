"""Library upsert / delete / list against a fake Firestore collection."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent import user_store


class _FakeDoc:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str):
        self._store = store
        self.id = doc_id

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        if merge and self.id in self._store:
            merged = {**self._store[self.id], **data}
            self._store[self.id] = merged
        else:
            self._store[self.id] = dict(data)

    def get(self) -> MagicMock:
        snap = MagicMock()
        exists = self.id in self._store
        snap.exists = exists
        snap.to_dict.return_value = dict(self._store[self.id]) if exists else None
        return snap


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}

    def document(self, doc_id: str) -> _FakeDoc:
        return _FakeDoc(self._docs, doc_id)

    def stream(self):
        for doc_id, data in self._docs.items():
            snap = MagicMock()
            snap.id = doc_id
            snap.to_dict.return_value = dict(data)
            yield snap


@pytest.fixture
def fake_library(monkeypatch: pytest.MonkeyPatch) -> _FakeCollection:
    library = _FakeCollection()
    mutations = _FakeCollection()

    monkeypatch.setattr(user_store, "_library", lambda uid: library)
    monkeypatch.setattr(user_store, "_mutations", lambda uid: mutations)
    return library


def test_upsert_list_and_delete_library(fake_library: _FakeCollection):
    result = user_store.upsert_library_item(
        "u1",
        item={
            "id": "lib_1",
            "name": "Gym Bowl",
            "kind": "meal",
            "origin": "user",
            "calories": 520,
            "proteinG": 40,
            "carbsG": 45,
            "fatG": 18,
            "servingGrams": 350,
            "ingredients": [{"name": "rice", "grams": 150}],
        },
        client_mutation_id="mut_1",
    )
    assert result == {"id": "lib_1"}

    # Idempotent replay
    again = user_store.upsert_library_item(
        "u1",
        item={"id": "lib_1", "name": "Gym Bowl v2"},
        client_mutation_id="mut_1",
    )
    assert again == {"id": "lib_1"}
    assert fake_library._docs["lib_1"]["name"] == "Gym Bowl"

    rows = user_store.list_library_items("u1")
    assert len(rows) == 1
    assert rows[0]["name"] == "Gym Bowl"
    assert rows[0]["ingredients"][0]["name"] == "rice"

    refs = user_store.library_refs_for_interpret("u1")
    assert refs[0]["id"] == "lib_1"
    assert "ingredients" not in refs[0]

    deleted = user_store.delete_library_item("u1", item_id="lib_1", client_mutation_id="mut_del")
    assert deleted == {"id": "lib_1"}
    assert user_store.list_library_items("u1") == []
    assert len(user_store.list_library_items("u1", include_deleted=True)) == 1


def test_upsert_requires_name(fake_library: _FakeCollection):
    with pytest.raises(ValueError, match="name"):
        user_store.upsert_library_item("u1", item={"id": "x"})
