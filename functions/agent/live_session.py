"""Vertex Gemini Live session bridged over WebSocket.

Reuses the harness prompt, memory pack, tool declarations, confirm gate, and
thread persistence from the text interpret_meal flow.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable

from agent.context_loader import resolve_interpret_request
from agent.harness.execute import run_calls
from agent.harness.format import format_message
from agent.harness.memory.assemble import build_pack
from agent.harness.messaging import sanitize_assistant_message
from agent.harness.outcomes import OutcomeError, normalize_outcome
from agent.harness.prompts import turn_prompt
from agent.harness.save_memory import proposals_for_utterance
from agent.llm.vertex import _function_declaration, get_vertex_live_client
from agent.thread_store import normalize_thread_id, persist_after_interpret
from agent.tools.registry import TOOL_DECLARATIONS
from agent.turn import empty_chat_outcome, unavailable
from schemas import InterpretMealRequest, InterpretMealResponse, WorkingMemory

logger = logging.getLogger("capy.live_session")

DEFAULT_LIVE_MODEL = "gemini-live-2.5-flash-native-audio"
DEFAULT_VOICE_NAME = "Puck"
VALID_VOICE_NAMES = {
    "Puck",
    "Charon",
    "Kore",
    "Fenrir",
    "Aoede",
    "Leda",
    "Orus",
    "Zephyr",
}
INPUT_AUDIO_MIME = "audio/pcm;rate=16000"


def live_model() -> str:
    return (os.environ.get("VERTEX_GEMINI_LIVE_MODEL") or DEFAULT_LIVE_MODEL).strip()


def normalize_voice_name(raw: str | None) -> str:
    candidate = (raw or "").strip()
    for name in VALID_VOICE_NAMES:
        if name.lower() == candidate.lower():
            return name
    return DEFAULT_VOICE_NAME


def build_live_connect_config(
    *,
    system: str,
    tool_declarations: list[dict[str, Any]],
    temperature: float,
    voice_name: str | None = None,
) -> Any:
    from google.genai import types

    resolved_voice = normalize_voice_name(voice_name)
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=system,
        temperature=temperature,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=resolved_voice,
                )
            )
        ),
        tools=[
            types.Tool(
                function_declarations=[
                    _function_declaration(spec, types) for spec in tool_declarations
                ]
            )
        ],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


def build_initial_turns(packed: dict[str, Any]) -> list[Any]:
    """Prior turns only. A trailing user turn makes Live answer immediately and loop."""
    from google.genai import types

    turns: list[Any] = []
    for item in packed.get("history") or []:
        role = item.get("role") if item.get("role") in ("user", "model") else "user"
        text = str(item.get("text") or "").strip()
        if text:
            turns.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
    while turns and getattr(turns[-1], "role", None) == "user":
        turns.pop()
    return turns


def build_turn_outcome(
    req: InterpretMealRequest,
    *,
    utterance: str,
    assistant_transcript: str,
    turn_outcome: dict[str, Any],
) -> tuple[dict[str, Any], InterpretMealRequest]:
    """Build the normalized InterpretMealResponse dict for one finished voice turn."""
    req_with_utterance = req.model_copy(update={"utterance": utterance})
    outcome = (
        dict(turn_outcome)
        if turn_outcome.get("intent")
        else empty_chat_outcome(model_text=assistant_transcript)
    )
    extra = [
        item.model_dump(mode="json") for item in proposals_for_utterance(req_with_utterance)
    ]
    facts = dict(outcome.get("phraseFacts") or {})
    if extra:
        outcome["memoryProposals"] = list(outcome.get("memoryProposals") or []) + extra
        facts["memory"] = list(facts.get("memory") or []) + extra

    draft = assistant_transcript.strip() or str(outcome.pop("_model_text", "") or "")
    message = format_message(draft=draft, outcome=facts)
    outcome["assistantMessage"] = sanitize_assistant_message(message, allow_empty=True)

    wm_raw = outcome.get("workingMemory")
    updated_req = req_with_utterance
    if isinstance(wm_raw, dict):
        try:
            wm = WorkingMemory.model_validate(wm_raw)
            conv = updated_req.conversation.model_copy(update={"workingMemory": wm})
            updated_req = updated_req.model_copy(update={"conversation": conv})
        except Exception:  # noqa: BLE001
            pass

    outcome.pop("phraseFacts", None)
    outcome.pop("_model_text", None)
    try:
        normalized = normalize_outcome(outcome)
        payload = InterpretMealResponse.model_validate(normalized).model_dump(mode="json")
    except (OutcomeError, Exception):  # noqa: BLE001
        payload = unavailable(["agent_unavailable", "outcome_invalid"])
    return payload, updated_req


class LiveTurnState:
    """Mutable state across one user-to-model turn inside a Live session."""

    def __init__(self) -> None:
        self.user_chunks: list[str] = []
        self.assistant_chunks: list[str] = []
        self.trace: list[dict[str, Any]] = []
        self.outcome: dict[str, Any] = {}

    def append_user(self, text: str) -> str:
        return _merge_transcript(self.user_chunks, text)

    def append_assistant(self, text: str) -> str:
        return _merge_transcript(self.assistant_chunks, text)

    @property
    def user_text(self) -> str:
        return "".join(self.user_chunks).strip()

    @property
    def assistant_text(self) -> str:
        return "".join(self.assistant_chunks).strip()

    def has_activity(self) -> bool:
        return bool(self.user_text or self.assistant_text or self.trace or self.outcome)


async def handle_tool_call(
    session: Any,
    req: InterpretMealRequest,
    uid: str,
    tool_call: Any,
    turn: LiveTurnState,
) -> InterpretMealRequest:
    """Execute Gemini Live function calls via run_calls and send FunctionResponses back."""
    from google.genai import types

    fcs = list(getattr(tool_call, "function_calls", None) or [])
    if not fcs:
        return req

    calls: list[dict[str, Any]] = []
    call_ids: list[str | None] = []
    for fc in fcs:
        name = str(getattr(fc, "name", None) or "")
        raw_args = getattr(fc, "args", None)
        args = dict(raw_args) if isinstance(raw_args, dict) else {}
        calls.append({"name": name, "arguments": args})
        call_ids.append(getattr(fc, "id", None))

    prior = len(turn.trace)
    turn.trace, turn.outcome = await asyncio.to_thread(
        run_calls, req, calls, uid=uid, trace=turn.trace
    )
    new_steps = turn.trace[prior:]

    wm_raw = turn.outcome.get("workingMemory")
    updated_req = req
    if isinstance(wm_raw, dict):
        try:
            wm = WorkingMemory.model_validate(wm_raw)
            conv = updated_req.conversation.model_copy(update={"workingMemory": wm})
            updated_req = updated_req.model_copy(update={"conversation": conv})
        except Exception:  # noqa: BLE001
            pass

    responses: list[Any] = []
    for idx, step in enumerate(new_steps):
        cid = call_ids[idx] if idx < len(call_ids) else None
        result = step.get("result")
        payload = result if isinstance(result, dict) else {"result": result}
        kwargs: dict[str, Any] = {
            "name": str(step.get("name") or ""),
            "response": payload,
        }
        if cid is not None:
            kwargs["id"] = cid
        responses.append(types.FunctionResponse(**kwargs))

    if responses:
        await session.send_tool_response(function_responses=responses)
    return updated_req


async def finish_turn(
    ws: Any,
    *,
    uid: str,
    thread_id: str,
    req: InterpretMealRequest,
    turn: LiveTurnState,
    persist_server_context: bool = True,
) -> InterpretMealRequest:
    """Finalize transcripts, emit final captions + outcome, and persist to Firestore."""
    user_text = turn.user_text
    assistant_text = turn.assistant_text
    if user_text:
        await ws.send_json(
            {"type": "user_transcript", "text": user_text, "final": True}
        )
    response, updated_req = build_turn_outcome(
        req,
        utterance=user_text,
        assistant_transcript=assistant_text,
        turn_outcome=turn.outcome,
    )
    final_assistant = str(response.get("assistantMessage") or assistant_text).strip()
    if final_assistant:
        await ws.send_json(
            {"type": "assistant_transcript", "text": final_assistant, "final": True}
        )

    if persist_server_context and "agent_unavailable" not in (response.get("warnings") or []):
        try:
            thread_view = await asyncio.to_thread(
                persist_after_interpret,
                uid,
                thread_id,
                user_text,
                response,
            )
            response["conversation"] = thread_view.get("conversation")
            response["messages"] = thread_view.get("messages") or []
            response["pageInfo"] = thread_view.get("pageInfo") or {
                "hasMore": False,
                "nextCursor": None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("live_session thread persist failed: %s", exc)

    await ws.send_json({"type": "outcome", **response})
    return updated_req


def _merge_transcript(chunks: list[str], text: str) -> str:
    """Join a Live caption. Cumulative updates replace; exact repeats are ignored."""
    piece = text or ""
    piece_stripped = piece.strip()
    current = "".join(chunks).strip()
    if not piece_stripped or piece_stripped == current:
        return current
    if current and piece_stripped.startswith(current):
        chunks.clear()
        chunks.append(piece_stripped)
        return piece_stripped
    if current.endswith(piece_stripped):
        return current
    chunks.append(piece)
    return "".join(chunks).strip()


def _extract_audio_bytes(server_content: Any) -> list[bytes]:
    chunks: list[bytes] = []
    model_turn = getattr(server_content, "model_turn", None)
    if model_turn is None:
        return chunks
    for part in getattr(model_turn, "parts", None) or []:
        inline = getattr(part, "inline_data", None)
        data = getattr(inline, "data", None) if inline is not None else None
        if isinstance(data, (bytes, bytearray)) and data:
            chunks.append(bytes(data))
    return chunks


async def pump_live_session(
    ws: Any,
    session: Any,
    *,
    uid: str,
    thread_id: str,
    req: InterpretMealRequest,
    persist_server_context: bool = True,
) -> InterpretMealRequest:
    """Bridge client WebSocket frames and Vertex Live messages until stop or disconnect."""
    from google.genai import types

    stop_event = asyncio.Event()
    state_holder: dict[str, Any] = {"req": req, "turn": LiveTurnState()}

    async def _client_to_vertex() -> None:
        try:
            while not stop_event.is_set():
                message = await ws.receive()
                msg_type = message.get("type")
                if msg_type == "websocket.disconnect":
                    stop_event.set()
                    break
                audio_bytes = message.get("bytes")
                if audio_bytes:
                    now = asyncio.get_running_loop().time()
                    ignore_until = state_holder.get("ignore_audio_until") or 0
                    if state_holder.get("model_busy") or now < ignore_until:
                        continue
                    await session.send_realtime_input(
                        audio=types.Blob(data=bytes(audio_bytes), mime_type=INPUT_AUDIO_MIME)
                    )
                    continue
                text_data = message.get("text")
                if not text_data:
                    continue
                import json

                try:
                    payload = json.loads(text_data)
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(payload, dict):
                    continue
                kind = payload.get("type")
                if kind == "stop":
                    try:
                        await session.send_realtime_input(audio_stream_end=True)
                    except Exception:  # noqa: BLE001
                        pass
                    stop_event.set()
                    break
        except Exception:  # noqa: BLE001
            stop_event.set()

    async def _vertex_to_client() -> None:
        try:
            while not stop_event.is_set():
                got_any = False
                async for server_msg in session.receive():
                    got_any = True
                    tool_call = getattr(server_msg, "tool_call", None)
                    if tool_call is not None:
                        state_holder["req"] = await handle_tool_call(
                            session,
                            state_holder["req"],
                            uid,
                            tool_call,
                            state_holder["turn"],
                        )

                    sc = getattr(server_msg, "server_content", None)
                    if sc is None:
                        continue

                    if getattr(sc, "interrupted", False):
                        await ws.send_json({"type": "interrupted"})

                    in_tr = getattr(sc, "input_transcription", None)
                    in_text = getattr(in_tr, "text", None) if in_tr is not None else None
                    if in_text:
                        combined = state_holder["turn"].append_user(str(in_text))
                        await ws.send_json(
                            {"type": "user_transcript", "text": combined, "final": False}
                        )

                    out_tr = getattr(sc, "output_transcription", None)
                    out_text = getattr(out_tr, "text", None) if out_tr is not None else None
                    if out_text:
                        state_holder["model_busy"] = True
                        combined = state_holder["turn"].append_assistant(str(out_text))
                        await ws.send_json(
                            {"type": "assistant_transcript", "text": combined, "final": False}
                        )

                    for pcm in _extract_audio_bytes(sc):
                        state_holder["model_busy"] = True
                        await ws.send_bytes(pcm)

                    if getattr(sc, "turn_complete", False):
                        turn: LiveTurnState = state_holder["turn"]
                        state_holder["model_busy"] = False
                        state_holder["ignore_audio_until"] = (
                            asyncio.get_running_loop().time() + 0.6
                        )
                        if turn.has_activity():
                            state_holder["req"] = await finish_turn(
                                ws,
                                uid=uid,
                                thread_id=thread_id,
                                req=state_holder["req"],
                                turn=turn,
                                persist_server_context=persist_server_context,
                            )
                            state_holder["turn"] = LiveTurnState()
                if not got_any:
                    break
            stop_event.set()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            if not stop_event.is_set():
                logger.warning("live_session vertex stream ended: %s", exc)
                try:
                    await ws.send_json(
                        {"type": "error", "message": "Voice session disconnected."}
                    )
                except Exception:  # noqa: BLE001
                    pass
                stop_event.set()

    client_task = asyncio.create_task(_client_to_vertex())
    vertex_task = asyncio.create_task(_vertex_to_client())
    try:
        await stop_event.wait()
    finally:
        for task in (client_task, vertex_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(client_task, vertex_task, return_exceptions=True)
        leftover: LiveTurnState = state_holder["turn"]
        if leftover.has_activity() and (leftover.trace or leftover.user_text):
            try:
                state_holder["req"] = await finish_turn(
                    ws,
                    uid=uid,
                    thread_id=thread_id,
                    req=state_holder["req"],
                    turn=leftover,
                    persist_server_context=persist_server_context,
                )
            except Exception:  # noqa: BLE001
                pass

    return state_holder["req"]


async def run_live_websocket(
    ws: Any,
    *,
    uid: str,
    session_factory: Callable[[str, Any], Any] | None = None,
) -> None:
    """Wait for the start message, connect to Vertex Live, and run the audio/tool loop."""
    import json

    start_payload: dict[str, Any] = {}
    try:
        first = await asyncio.wait_for(ws.receive(), timeout=15.0)
        if first.get("type") == "websocket.disconnect":
            return
        raw_text = first.get("text") or "{}"
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            start_payload = parsed
    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"type": "error", "message": f"Invalid start message: {exc}"})
        return

    if start_payload.get("type") not in {None, "start"}:
        await ws.send_json({"type": "error", "message": "Expected start message."})
        return

    thread_id = normalize_thread_id(start_payload.get("threadId"))
    use_server_context = start_payload.get("useServerContext", True) is not False
    raw_req = dict(start_payload)
    raw_req["threadId"] = thread_id
    raw_req["useServerContext"] = use_server_context
    raw_req.setdefault("utterance", "")

    try:
        req = await asyncio.to_thread(resolve_interpret_request, uid, raw_req)
        context_pack = await asyncio.to_thread(build_pack, req)
        packed = turn_prompt(req, context_pack)
    except Exception as exc:  # noqa: BLE001
        logger.warning("live_session context load failed: %s", exc)
        await ws.send_json({"type": "error", "message": "Could not load user context."})
        return

    system = str(packed["system"])
    user_context = str(packed.get("user") or "").strip()
    if user_context:
        system = (
            f"{system}\n\nSession context. Wait until the user speaks. "
            f"Do not answer this block and do not repeat a previous reply.\n{user_context}"
        )
    raw_voice = str(start_payload.get("voiceName") or "").strip()
    if not raw_voice and use_server_context:
        try:
            from agent.user_store import get_profile

            profile = await asyncio.to_thread(get_profile, uid)
            raw_voice = str(profile.get("voiceName") or "").strip()
        except Exception:  # noqa: BLE001
            raw_voice = ""
    voice_name = normalize_voice_name(raw_voice)

    config = build_live_connect_config(
        system=system,
        tool_declarations=TOOL_DECLARATIONS,
        temperature=float(packed["temperature"]),
        voice_name=voice_name,
    )
    model_name = live_model()

    def _default_factory(model: str, cfg: Any) -> Any:
        client = get_vertex_live_client()
        return client.aio.live.connect(model=model, config=cfg)

    factory = session_factory or _default_factory
    try:
        async with factory(model_name, config) as session:
            initial_turns = build_initial_turns(packed)
            if initial_turns and hasattr(session, "send_client_content"):
                await session.send_client_content(turns=initial_turns, turn_complete=False)
            await ws.send_json({"type": "ready", "threadId": thread_id, "dayKey": req.dayKey})
            await pump_live_session(
                ws,
                session,
                uid=uid,
                thread_id=thread_id,
                req=req,
                persist_server_context=use_server_context,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("live_session connect/run failed: %s", exc)
        try:
            await ws.send_json({"type": "error", "message": "Voice session unavailable."})
        except Exception:  # noqa: BLE001
            pass
