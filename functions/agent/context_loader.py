"""Build InterpretMealRequest from Firestore (server source of truth)."""

from __future__ import annotations

from typing import Any

from agent.thread_store import conversation_for_interpret, normalize_thread_id
from agent.user_store import (
    build_diary_context,
    day_key_for_timezone,
    get_profile,
    long_term_from_profile,
    preference_context_from_profile,
)
from agent.llm.response_style import normalize_response_style
from schemas import (
    InterpretContext,
    InterpretMealRequest,
    request_from_dict,
)


def _interpret_context_from_raw(raw: dict[str, Any], profile: dict[str, Any]) -> InterpretContext:
    block = raw.get("context") if isinstance(raw.get("context"), dict) else {}
    assistance = block.get("assistanceLevel") or profile.get("assistanceLevel") or "fullAssist"
    style = block.get("responseStyle") or profile.get("responseStyle")
    return InterpretContext(
        assistanceLevel=str(assistance),
        responseStyle=normalize_response_style(str(style) if style is not None else None),
        lastIntent=block.get("lastIntent"),
    )


def load_interpret_request(uid: str, raw: dict[str, Any]) -> InterpretMealRequest:
    """Merge Firestore profile, diary, and conversation thread with the utterance."""
    profile = get_profile(uid)
    timezone = str(raw.get("timezone") or profile.get("timezone") or "UTC")
    day_key = str(raw.get("dayKey") or day_key_for_timezone(timezone))
    thread_id = normalize_thread_id(raw.get("threadId"))
    utterance = str(raw.get("utterance") or "")
    diary = build_diary_context(uid, day_key, profile)
    conversation = conversation_for_interpret(uid, thread_id, utterance)
    ctx = _interpret_context_from_raw(raw, profile)
    wm = conversation.workingMemory
    if wm and wm.pendingIntent:
        ctx = InterpretContext(
            assistanceLevel=ctx.assistanceLevel,
            responseStyle=ctx.responseStyle,
            lastIntent=wm.pendingIntent,
        )
    base = {
        "utterance": utterance,
        "timezone": timezone,
        "dayKey": day_key,
        "preferenceContext": preference_context_from_profile(profile).model_dump(),
        "diaryContext": diary.model_dump(mode="json"),
        "longTermMemory": [n.model_dump() for n in long_term_from_profile(profile)],
        "conversation": conversation.model_dump(mode="json"),
        "context": ctx.model_dump(mode="json"),
    }
    if raw.get("memorySnapshot") is not None:
        base["memorySnapshot"] = raw.get("memorySnapshot")
    # Client snapshot of local SwiftData library (not stored in Firestore yet).
    if isinstance(raw.get("libraryContext"), list):
        base["libraryContext"] = raw.get("libraryContext")
    return InterpretMealRequest.model_validate(base)


def resolve_interpret_request(uid: str, raw: dict[str, Any]) -> InterpretMealRequest:
    """Client snapshot when present; otherwise load from Firestore."""
    if raw.get("useServerContext") is True:
        return load_interpret_request(uid, raw)
    return request_from_dict(raw)
