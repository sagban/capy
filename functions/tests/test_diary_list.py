"""Diary list against a fake Firestore entries collection."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from agent import user_store


class _FakeDoc:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str):
        self._store = store
        self.id = doc_id

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        if merge and self.id in self._store:
            self._store[self.id] = {**self._store[self.id], **data}
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


def test_list_diary_returns_confirmed_and_can_include_deleted(monkeypatch):
    entries = _FakeCollection()
    mutations = _FakeCollection()
    monkeypatch.setattr(user_store, "_entries", lambda uid, day: entries)
    monkeypatch.setattr(user_store, "_mutations", lambda uid: mutations)
    monkeypatch.setattr(user_store, "_day_keys", lambda uid: ["2026-10-23"])

    written = user_store.log_meal(
        "u1",
        day_key="2026-10-23",
        meal_slot="Lunch",
        items=[
            {
                "name": "Egg",
                "grams": 50,
                "per100g": {"calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11},
            }
        ],
        entry_id="11111111-1111-1111-1111-111111111111",
    )
    assert written["entryId"] == "11111111-1111-1111-1111-111111111111"

    rows = user_store.list_diary_meals("u1")
    assert len(rows) == 1
    assert rows[0]["dayKey"] == "2026-10-23"
    assert rows[0]["mealSlot"] == "Lunch"
    assert rows[0]["items"][0]["name"] == "Egg"
    assert rows[0]["deleted"] is False

    user_store.delete_entry(
        "u1",
        day_key="2026-10-23",
        entry_id="11111111-1111-1111-1111-111111111111",
    )
    assert user_store.list_diary_meals("u1") == []
    deleted = user_store.list_diary_meals("u1", include_deleted=True)
    assert len(deleted) == 1
    assert deleted[0]["deleted"] is True
    assert deleted[0]["confirmed"] is False
