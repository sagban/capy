"""Gemini Live WebSocket session tests with a fake Live session."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from google.genai import types

from agent import live_session
from schemas import (
    ConversationContext,
    DiaryContext,
    InterpretContext,
    InterpretMealRequest,
    MacroTotals,
    PreferenceContext,
)


def _sample_request() -> InterpretMealRequest:
    return InterpretMealRequest(
        utterance="",
        timezone="UTC",
        dayKey="2026-10-23",
        preferenceContext=PreferenceContext(),
        diaryContext=DiaryContext(
            today=[],
            previousDays=[],
            remaining=MacroTotals(calories=1800, proteinG=120, carbsG=180, fatG=60),
        ),
        longTermMemory=[],
        conversation=ConversationContext(threadId="default"),
        context=InterpretContext(assistanceLevel="fullAssist", responseStyle="balanced"),
    )


class _FakeWebSocket:
    def __init__(self, incoming: list[dict[str, Any]]) -> None:
        self._incoming = asyncio.Queue[dict[str, Any]]()
        for item in incoming:
            self._incoming.put_nowait(item)
        self.sent_json: list[dict[str, Any]] = []
        self.sent_bytes: list[bytes] = []

    async def receive(self) -> dict[str, Any]:
        return await self._incoming.get()

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent_json.append(data)

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)


class _FakeLiveSession:
    """Scripted multi-turn Live session that yields tool calls, audio, and turn_complete."""

    def __init__(self, turns: list[list[types.LiveServerMessage]]) -> None:
        self._turns = list(turns)
        self.client_contents: list[tuple[Any, bool]] = []
        self.realtime_inputs: list[dict[str, Any]] = []
        self.tool_responses: list[list[types.FunctionResponse]] = []

    async def __aenter__(self) -> "_FakeLiveSession":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def send_client_content(self, *, turns: Any = None, turn_complete: bool = True) -> None:
        self.client_contents.append((turns, turn_complete))

    async def send_realtime_input(self, **kwargs: Any) -> None:
        self.realtime_inputs.append(kwargs)

    async def send_tool_response(self, *, function_responses: Any) -> None:
        self.tool_responses.append(list(function_responses))

    async def receive(self):
        if not self._turns:
            return
        batch = self._turns.pop(0)
        for msg in batch:
            yield msg


def test_initial_turns_wait_for_live_audio():
    turns = live_session.build_initial_turns(
        {
            "history": [
                {"role": "user", "text": "eggs"},
                {"role": "model", "text": "logged"},
                {"role": "user", "text": "thanks"},
            ],
            "user": "context pack\n\nUser message:\n",
        }
    )
    assert [turn.role for turn in turns] == ["user", "model"]


def test_transcript_chunks_do_not_repeat():
    chunks: list[str] = []
    assert live_session._merge_transcript(chunks, "Hello") == "Hello"
    assert live_session._merge_transcript(chunks, "Hello there") == "Hello there"
    assert live_session._merge_transcript(chunks, "Hello there") == "Hello there"
    assert live_session._merge_transcript(chunks, " there") == "Hello there"
    assert live_session._merge_transcript(chunks, "Hello there") == "Hello there"


def test_live_session_stages_write_and_persists_turn(monkeypatch: pytest.MonkeyPatch):
    persisted_calls: list[dict[str, Any]] = []
    written_entries: list[dict[str, Any]] = []

    monkeypatch.setattr(
        live_session,
        "resolve_interpret_request",
        lambda uid, raw: _sample_request(),
    )

    def _fake_persist(uid: str, thread_id: str, utterance: str, response: dict[str, Any]) -> dict[str, Any]:
        persisted_calls.append(
            {
                "uid": uid,
                "thread_id": thread_id,
                "utterance": utterance,
                "response": dict(response),
            }
        )
        return {
            "conversation": {"threadId": thread_id, "recentTurns": []},
            "messages": [{"role": "user", "text": utterance}],
            "pageInfo": {"hasMore": False, "nextCursor": None},
        }

    monkeypatch.setattr(live_session, "persist_after_interpret", _fake_persist)

    def _fake_write_food_entry(uid: str, day_key: str, meal_slot: str, kind: str, name: str, grams: float, per100g: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        written_entries.append(
            {"uid": uid, "day_key": day_key, "meal_slot": meal_slot, "name": name, "grams": grams}
        )
        return {"entryId": "entry-1", "dayKey": day_key}

    monkeypatch.setattr("agent.tools.diary_io.write_food_entry", _fake_write_food_entry)

    write_args = {
        "day_key": "2026-10-23",
        "meal_slot": "Breakfast",
        "kind": "food",
        "name": "Scrambled eggs",
        "grams": 150.0,
        "foodId": "egg_scrambled",
        "source": "catalog",
        "per100g": {"calories": 148.0, "proteinG": 10.0, "carbsG": 1.6, "fatG": 11.0},
    }

    turn_1 = [
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(text="Log two scrambled eggs")
            )
        ),
        types.LiveServerMessage(
            tool_call=types.LiveServerToolCall(
                function_calls=[
                    types.FunctionCall(
                        id="call-1",
                        name="write_food_entry",
                        args=write_args,
                    )
                ]
            )
        ),
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                model_turn=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                data=b"\x01\x02\x03\x04",
                                mime_type="audio/pcm;rate=24000",
                            )
                        )
                    ],
                ),
                output_transcription=types.Transcription(
                    text="Staged 150g of scrambled eggs for Breakfast. Confirm to log it?"
                ),
                turn_complete=True,
            )
        ),
    ]

    turn_2 = [
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(text="Yes, log it")
            )
        ),
        types.LiveServerMessage(
            tool_call=types.LiveServerToolCall(
                function_calls=[
                    types.FunctionCall(
                        id="call-2",
                        name="write_food_entry",
                        args=write_args,
                    )
                ]
            )
        ),
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                output_transcription=types.Transcription(text="Logged scrambled eggs."),
                turn_complete=True,
            )
        ),
    ]

    fake_session = _FakeLiveSession([turn_1, turn_2])
    ws = _FakeWebSocket(
        [
            {"type": "websocket.receive", "text": json.dumps({"type": "start", "threadId": "default", "dayKey": "2026-10-23"})},
            {"type": "websocket.receive", "bytes": b"\x00\x00" * 160},
        ]
    )

    asyncio.run(
        live_session.run_live_websocket(
            ws,
            uid="user-123",
            session_factory=lambda _model, _cfg: fake_session,
        )
    )

    # Context stays on the system prompt. A user turn here makes Live speak immediately.
    assert fake_session.client_contents == []
    assert ws.sent_json[0]["type"] == "ready"
    assert ws.sent_bytes == [b"\x01\x02\x03\x04"]

    # 2. First tool call staged confirm_log; second tool call confirmed and wrote
    assert len(fake_session.tool_responses) == 2
    first_resp = fake_session.tool_responses[0][0]
    assert first_resp.id == "call-1"
    assert first_resp.name == "write_food_entry"
    assert first_resp.response["staged"] is True
    assert first_resp.response["pendingType"] == "confirm_log"

    second_resp = fake_session.tool_responses[1][0]
    assert second_resp.id == "call-2"
    assert second_resp.response["wrote"] is True
    assert second_resp.response["entryId"] == "entry-1"
    assert len(written_entries) == 1

    # 3. Both turns emitted outcomes and persisted via persist_after_interpret
    outcomes = [msg for msg in ws.sent_json if msg.get("type") == "outcome"]
    assert len(outcomes) == 2
    assert outcomes[0]["pendingAction"]["type"] == "confirm_log"
    assert outcomes[0]["pendingAction"]["payload"]["resolvedItems"][0]["displayName"] == "Scrambled eggs"
    assert outcomes[1]["pendingAction"] is None
    assert outcomes[1]["intent"] == "log_meal"

    assert len(persisted_calls) == 2
    assert persisted_calls[0]["utterance"] == "Log two scrambled eggs"
    assert persisted_calls[0]["response"]["pendingAction"]["type"] == "confirm_log"
    assert persisted_calls[1]["utterance"] == "Yes, log it"
    assert persisted_calls[1]["response"]["pendingAction"] is None


def test_live_session_interrupted_and_memory_proposal(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        live_session,
        "resolve_interpret_request",
        lambda uid, raw: _sample_request(),
    )
    monkeypatch.setattr(
        live_session,
        "persist_after_interpret",
        lambda uid, thread_id, utterance, response: {
            "conversation": {"threadId": thread_id, "recentTurns": []},
            "messages": [],
            "pageInfo": {"hasMore": False, "nextCursor": None},
        },
    )

    turn_1 = [
        types.LiveServerMessage(
            server_content=types.LiveServerContent(interrupted=True)
        ),
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(text="Remember I love oat milk"),
                output_transcription=types.Transcription(text="Noted oat milk."),
                turn_complete=True,
            )
        ),
    ]

    fake_session = _FakeLiveSession([turn_1])
    ws = _FakeWebSocket(
        [
            {"type": "websocket.receive", "text": json.dumps({"type": "start", "threadId": "default", "dayKey": "2026-10-23"})},
        ]
    )

    asyncio.run(
        live_session.run_live_websocket(
            ws,
            uid="user-123",
            session_factory=lambda _model, _cfg: fake_session,
        )
    )

    types_sent = [msg.get("type") for msg in ws.sent_json]
    assert "interrupted" in types_sent
    outcomes = [msg for msg in ws.sent_json if msg.get("type") == "outcome"]
    assert len(outcomes) == 1
    assert outcomes[0]["memoryProposals"] == [{"action": "add", "text": "I love oat milk", "id": None}]


def test_live_session_applies_voice_name_to_connect_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        live_session,
        "resolve_interpret_request",
        lambda uid, raw: _sample_request(),
    )

    captured_configs: list[Any] = []
    fake_session = _FakeLiveSession([])

    def _factory(_model: str, cfg: Any) -> _FakeLiveSession:
        captured_configs.append(cfg)
        return fake_session

    ws = _FakeWebSocket(
        [
            {
                "type": "websocket.receive",
                "text": json.dumps(
                    {"type": "start", "threadId": "default", "dayKey": "2026-10-23", "voiceName": "Fenrir"}
                ),
            },
        ]
    )

    asyncio.run(
        live_session.run_live_websocket(
            ws,
            uid="user-123",
            session_factory=_factory,
        )
    )

    assert len(captured_configs) == 1
    voice_cfg = captured_configs[0].speech_config.voice_config.prebuilt_voice_config
    assert voice_cfg.voice_name == "Fenrir"

