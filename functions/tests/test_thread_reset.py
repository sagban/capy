"""patch_thread reset deletes the message archive and clears the thread doc."""

from __future__ import annotations

from typing import Any

import pytest
from firebase_functions import https_fn

from agent import thread_store
from agent.tools.registry import TOOL_DECLARATIONS as _TOOL_DECLARATIONS
from user_api import patch_thread_for_uid

_ = _TOOL_DECLARATIONS


class _Ref:
    def __init__(self, coll: "_Docs", doc_id: str):
        self.coll = coll
        self.id = doc_id


class _Snap:
    def __init__(self, coll: "_Docs", doc_id: str, data: dict[str, Any]):
        self.id = doc_id
        self.reference = _Ref(coll, doc_id)
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class _Query:
    def __init__(self, coll: "_Docs", limit: int):
        self.coll = coll
        self.limit = limit

    def stream(self):
        items = list(self.coll.docs.items())[: self.limit]
        return [_Snap(self.coll, doc_id, data) for doc_id, data in items]


class _Docs:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def limit(self, count: int) -> _Query:
        return _Query(self, count)

    def document(self, doc_id: str) -> "_Doc":
        return _Doc(self, doc_id)


class _Doc:
    def __init__(self, coll: _Docs, doc_id: str):
        self.coll = coll
        self.id = doc_id

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        self.coll.docs[self.id] = dict(data)


class _Batch:
    def __init__(self) -> None:
        self._refs: list[_Ref] = []

    def delete(self, ref: _Ref) -> None:
        self._refs.append(ref)

    def commit(self) -> None:
        for ref in self._refs:
            ref.coll.docs.pop(ref.id, None)
        self._refs.clear()


class _Db:
    def batch(self) -> _Batch:
        return _Batch()


def test_reset_deletes_messages_past_one_batch(monkeypatch: pytest.MonkeyPatch):
    messages = _Docs()
    threads = _Docs()
    for index in range(450):
        messages.docs[f"m{index}"] = {"messageId": f"m{index}", "text": "eggs", "seq": index}
    threads.docs["default"] = {
        "threadId": "default",
        "summary": "old chat",
        "recentTurns": [{"role": "user", "text": "eggs"}],
        "nextSeq": 450,
    }

    monkeypatch.setattr(thread_store, "_messages", lambda uid, thread_id: messages)
    monkeypatch.setattr(thread_store, "_threads", lambda uid: threads)
    monkeypatch.setattr("agent.user_store.get_db", lambda: _Db())

    page = patch_thread_for_uid("u1", {"threadId": "default", "reset": True, "assistantText": "keep me"})

    assert messages.docs == {}
    stored = threads.docs["default"]
    assert stored["summary"] == ""
    assert stored["recentTurns"] == []
    assert stored["nextSeq"] == 0
    assert page["messages"] == []
    assert page["pageInfo"]["hasMore"] is False
    assert page["conversation"]["summary"] == ""


def test_patch_thread_still_requires_a_change():
    with pytest.raises(https_fn.HttpsError) as caught:
        patch_thread_for_uid("u1", {"threadId": "default"})
    assert caught.value.code == https_fn.FunctionsErrorCode.INVALID_ARGUMENT
    assert "reset is required" in caught.value.message
