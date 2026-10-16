"""Firestore conversation threads: users/{uid}/threads/{threadId} + messages archive."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from google.cloud.firestore_v1 import FieldFilter
from google.cloud.firestore_v1.base_query import BaseQuery

from schemas import ConversationContext, ConversationTurn, WorkingMemory

logger = logging.getLogger("capy.thread_store")

DEFAULT_THREAD_ID = "default"
WINDOW_SIZE = 12
DEFAULT_PAGE_LIMIT = 12
MAX_PAGE_LIMIT = 50
SUMMARY_MAX = 1200


def normalize_thread_id(raw: Any) -> str:
    text = str(raw or "").strip()
    return text or DEFAULT_THREAD_ID


def clamp_page_limit(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_LIMIT
    return max(1, min(value, MAX_PAGE_LIMIT))


def _threads(uid: str):
    from agent.user_store import _users

    return _users(uid).collection("threads")


def _messages(uid: str, thread_id: str):
    return _threads(uid).document(thread_id).collection("messages")


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _compact(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split())


def default_thread_dict(thread_id: str = DEFAULT_THREAD_ID) -> dict[str, Any]:
    return {
        "threadId": thread_id,
        "summary": "",
        "recentTurns": [],
        "workingMemory": None,
        "nextSeq": 0,
        "updatedAt": _now_iso(),
    }


def _ensure_thread_document(uid: str, thread_id: str):
    ref = _threads(uid).document(thread_id)
    snap = ref.get()
    if not snap.exists:
        ref.set(default_thread_dict(thread_id))
    return ref


def get_conversation(uid: str, thread_id: str = DEFAULT_THREAD_ID) -> ConversationContext:
    snap = _threads(uid).document(thread_id).get()
    if not snap.exists:
        return ConversationContext(threadId=thread_id)
    data = snap.to_dict() or {}
    return _conversation_from_doc(data, thread_id)


def _conversation_from_doc(data: dict[str, Any], thread_id: str) -> ConversationContext:
    turns_raw = data.get("recentTurns") or []
    turns: list[ConversationTurn] = []
    if isinstance(turns_raw, list):
        for item in turns_raw:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            text = str(item.get("text") or "")
            if role:
                turns.append(ConversationTurn(role=role, text=text))
    wm_raw = data.get("workingMemory")
    wm = None
    if isinstance(wm_raw, dict) and wm_raw:
        try:
            wm = WorkingMemory.model_validate(wm_raw)
        except Exception:  # noqa: BLE001
            wm = None
    return ConversationContext(
        threadId=str(data.get("threadId") or thread_id),
        summary=str(data.get("summary") or ""),
        recentTurns=turns,
        workingMemory=wm,
    )


def _conversation_api_dict(conversation: ConversationContext) -> dict[str, Any]:
    """Thread metadata for clients (rolling window stays server-side for the harness)."""
    return {
        "threadId": conversation.threadId,
        "summary": conversation.summary or "",
        "workingMemory": (
            conversation.workingMemory.model_dump(mode="json")
            if conversation.workingMemory
            else None
        ),
        "recentTurns": [],
    }


def _message_to_api(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "messageId": str(data.get("messageId") or ""),
        "role": str(data.get("role") or ""),
        "text": str(data.get("text") or ""),
        "createdAt": str(data.get("createdAt") or ""),
        "seq": int(data.get("seq") or 0),
    }


def archive_message(uid: str, thread_id: str, role: str, text: str) -> str:
    """Append one durable message; returns messageId."""
    from firebase_admin import firestore

    from agent.user_store import get_db

    db = get_db()
    thread_ref = _ensure_thread_document(uid, thread_id)
    message_id = str(uuid.uuid4())

    @firestore.transactional
    def _txn(transaction, ref: Any, mid: str, turn_role: str, body: str) -> str:
        snap = ref.get(transaction=transaction)
        data = snap.to_dict() if snap.exists else default_thread_dict(thread_id)
        seq = int(data.get("nextSeq") or 0)
        now = _now_iso()
        msg_ref = ref.collection("messages").document(mid)
        transaction.set(
            msg_ref,
            {
                "messageId": mid,
                "role": turn_role,
                "text": body,
                "seq": seq,
                "createdAt": now,
            },
        )
        transaction.set(
            ref,
            {
                "threadId": thread_id,
                "nextSeq": seq + 1,
                "updatedAt": now,
            },
            merge=True,
        )
        return mid

    transaction = db.transaction()
    return _txn(transaction, thread_ref, message_id, role, text)


def list_messages_page(
    uid: str,
    thread_id: str,
    *,
    limit: int = DEFAULT_PAGE_LIMIT,
    cursor: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return chronological messages (oldest→newest within the page). Cursor = oldest messageId already shown."""
    coll = _messages(uid, thread_id)
    query = coll.order_by("seq", direction=BaseQuery.DESCENDING)
    if cursor:
        cursor_snap = coll.document(cursor).get()
        if cursor_snap.exists:
            before_seq = int((cursor_snap.to_dict() or {}).get("seq", 0))
            query = query.where(filter=FieldFilter("seq", "<", before_seq))
    docs = list(query.limit(limit).stream())
    docs.reverse()
    messages = [_message_to_api(doc.to_dict() or {}) for doc in docs]
    has_more = False
    next_cursor = None
    if docs:
        oldest = docs[0].to_dict() or {}
        oldest_seq = int(oldest.get("seq", 0))
        probe = coll.where(filter=FieldFilter("seq", "<", oldest_seq)).limit(1).get()
        has_more = len(probe) > 0
        if has_more:
            next_cursor = str(oldest.get("messageId") or "")
    page_info = {"hasMore": has_more, "nextCursor": next_cursor}
    return messages, page_info


def get_thread_view(
    uid: str,
    thread_id: str,
    *,
    limit: int = DEFAULT_PAGE_LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    conversation = get_conversation(uid, thread_id)
    messages, page_info = list_messages_page(uid, thread_id, limit=limit, cursor=cursor)
    return {
        "conversation": _conversation_api_dict(conversation),
        "messages": messages,
        "pageInfo": page_info,
    }


def save_conversation(uid: str, thread_id: str, conversation: ConversationContext) -> None:
    payload = {
        "threadId": thread_id,
        "summary": conversation.summary or "",
        "recentTurns": [t.model_dump(mode="json") for t in (conversation.recentTurns or [])],
        "workingMemory": (
            conversation.workingMemory.model_dump(mode="json")
            if conversation.workingMemory
            else None
        ),
        "updatedAt": _now_iso(),
    }
    _threads(uid).document(thread_id).set(payload, merge=True)


def _trim_conversation(conversation: ConversationContext) -> ConversationContext:
    turns = list(conversation.recentTurns or [])
    if len(turns) <= WINDOW_SIZE:
        return conversation
    overflow = turns[: len(turns) - WINDOW_SIZE]
    turns = turns[len(turns) - WINDOW_SIZE :]
    folded = " · ".join(
        f"{'user' if t.role == 'user' else 'capy'}: {_compact(t.text)[:200]}"
        for t in overflow
    )
    summary = conversation.summary or ""
    if not summary:
        summary = folded
    else:
        summary = _compact(f"{summary} · {folded}")
    if len(summary) > SUMMARY_MAX:
        summary = summary[-SUMMARY_MAX:]
    return ConversationContext(
        threadId=conversation.threadId,
        summary=summary,
        recentTurns=turns,
        workingMemory=conversation.workingMemory,
    )


def conversation_for_interpret(
    uid: str,
    thread_id: str,
    utterance: str,
) -> ConversationContext:
    """Load stored rolling window and append the in-flight user utterance (in-memory only)."""
    conv = get_conversation(uid, thread_id)
    text = (utterance or "").strip()
    if not text:
        return conv
    turns = list(conv.recentTurns or [])
    if turns and turns[-1].role == "user" and _compact(turns[-1].text) == _compact(text):
        return conv
    turns.append(ConversationTurn(role="user", text=text))
    return ConversationContext(
        threadId=thread_id,
        summary=conv.summary,
        recentTurns=turns,
        workingMemory=conv.workingMemory,
    )


def _working_memory_from_response(response: dict[str, Any]) -> WorkingMemory | None:
    raw = response.get("workingMemory")
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return WorkingMemory.model_validate(raw)
    except Exception:  # noqa: BLE001
        return None


def _should_persist_assistant(response: dict[str, Any]) -> bool:
    msg = (response.get("assistantMessage") or "").strip()
    pending = response.get("pendingAction")
    if isinstance(pending, dict) and pending:
        return True
    if msg:
        return True
    if response.get("memoryProposals"):
        return True
    if response.get("suggestionOptions"):
        return True
    return False


def _thread_view_after_mutation(
    uid: str,
    thread_id: str,
    conversation: ConversationContext,
) -> dict[str, Any]:
    messages, page_info = list_messages_page(uid, thread_id, limit=DEFAULT_PAGE_LIMIT)
    return {
        "conversation": _conversation_api_dict(conversation),
        "messages": messages,
        "pageInfo": page_info,
    }


def persist_after_interpret(
    uid: str,
    thread_id: str,
    utterance: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    """Archive new turns, update rolling window + summary, return latest page for the client."""
    _ensure_thread_document(uid, thread_id)
    conv = get_conversation(uid, thread_id)
    text = (utterance or "").strip()
    turns = list(conv.recentTurns or [])
    if text:
        if not (turns and turns[-1].role == "user" and _compact(turns[-1].text) == _compact(text)):
            archive_message(uid, thread_id, "user", text)
            turns.append(ConversationTurn(role="user", text=text))
    if _should_persist_assistant(response):
        reply = (response.get("assistantMessage") or "").strip()
        archive_message(uid, thread_id, "assistant", reply)
        turns.append(ConversationTurn(role="assistant", text=reply))
    wm = _working_memory_from_response(response)
    conv = ConversationContext(
        threadId=thread_id,
        summary=conv.summary,
        recentTurns=turns,
        workingMemory=wm,
    )
    conv = _trim_conversation(conv)
    save_conversation(uid, thread_id, conv)
    return _thread_view_after_mutation(uid, thread_id, conv)


def append_assistant_turn(
    uid: str,
    thread_id: str,
    text: str,
    *,
    clear_working_memory: bool = False,
) -> dict[str, Any]:
    _ensure_thread_document(uid, thread_id)
    conv = get_conversation(uid, thread_id)
    body = text.strip()
    archive_message(uid, thread_id, "assistant", body)
    turns = list(conv.recentTurns or [])
    turns.append(ConversationTurn(role="assistant", text=body))
    wm = None if clear_working_memory else conv.workingMemory
    conv = ConversationContext(
        threadId=thread_id,
        summary=conv.summary,
        recentTurns=turns,
        workingMemory=wm,
    )
    conv = _trim_conversation(conv)
    save_conversation(uid, thread_id, conv)
    return _thread_view_after_mutation(uid, thread_id, conv)


def note_day_rollover(
    uid: str,
    thread_id: str,
    previous_day_key: str,
    meal_count: int,
) -> dict[str, Any]:
    _ensure_thread_document(uid, thread_id)
    conv = get_conversation(uid, thread_id)
    note = f"new day — prior day {previous_day_key} logged {meal_count} meals"
    summary = conv.summary or ""
    if not summary:
        summary = note
    elif note not in summary:
        summary = _compact(f"{summary} · {note}")
    if len(summary) > SUMMARY_MAX:
        summary = summary[-SUMMARY_MAX:]
    conv = ConversationContext(
        threadId=thread_id,
        summary=summary,
        recentTurns=list(conv.recentTurns or []),
        workingMemory=conv.workingMemory,
    )
    save_conversation(uid, thread_id, conv)
    return _thread_view_after_mutation(uid, thread_id, conv)
