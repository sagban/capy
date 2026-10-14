"""Scripted model turns for offline tests. Replaces model_turn and phrase only."""

from __future__ import annotations

from typing import Any

_QUEUE: list[dict[str, Any]] = []


def push_mock_turns(turns: list[dict[str, Any]]) -> None:
    _QUEUE.clear()
    _QUEUE.extend(turns)


def pop_mock_turn() -> dict[str, Any] | None:
    if not _QUEUE:
        return None
    return _QUEUE.pop(0)


def clear_mock_turns() -> None:
    _QUEUE.clear()
