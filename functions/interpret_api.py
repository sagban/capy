"""interpret_meal handler (shared by Firebase callable and Cloud Run HTTP/MCP)."""

from __future__ import annotations

import logging
from typing import Any

import phoenix_tracing

from agent.context_loader import resolve_interpret_request
from agent.graph import run_interpret
from agent.thread_store import normalize_thread_id, persist_after_interpret

logger = logging.getLogger("capy.interpret_meal")


def interpret_meal_for_uid(uid: str, raw: dict[str, Any]) -> dict[str, Any]:
    utterance = str(raw.get("utterance") or "")[:80]
    use_server_context = raw.get("useServerContext") is True
    thread_id = normalize_thread_id(raw.get("threadId"))
    logger.info("interpret_meal start uid=%s utterance=%r", uid, utterance)
    parsed = resolve_interpret_request(uid, raw)

    try:
        with phoenix_tracing.chain_span("interpret_meal", input_value=utterance) as root:
            response = run_interpret(parsed.model_dump(mode="json"), uid=uid)
            for candidate in response.get("candidates") or []:
                if not isinstance(candidate, dict):
                    continue
                source = (candidate.get("source") or "").lower()
                for key in ("calories", "proteinG", "carbsG", "fatG"):
                    candidate.pop(key, None)
                if source not in {"web", "diary"} and not source.startswith("web"):
                    candidate.pop("per100g", None)
            phoenix_tracing.set_output(
                root,
                {
                    "intent": response.get("intent"),
                    "assistantMessage": response.get("assistantMessage"),
                    "pendingAction": (response.get("pendingAction") or {}).get("type")
                    if isinstance(response.get("pendingAction"), dict)
                    else None,
                    "warnings": response.get("warnings"),
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("interpret_meal run failed: %s", exc)
        return {
            "intent": "unknown",
            "candidates": [],
            "assistantMessage": "",
            "warnings": ["agent_unavailable"],
            "memoryProposals": [],
            "pendingAction": None,
            "suggestionOptions": [],
        }

    if use_server_context and "agent_unavailable" not in (response.get("warnings") or []):
        try:
            thread_view = persist_after_interpret(
                uid,
                thread_id,
                str(raw.get("utterance") or ""),
                response,
            )
            response["conversation"] = thread_view.get("conversation")
            response["messages"] = thread_view.get("messages") or []
            response["pageInfo"] = thread_view.get("pageInfo") or {
                "hasMore": False,
                "nextCursor": None,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("interpret_meal thread persist failed: %s", exc)

    logger.info(
        "interpret_meal done intent=%s msg_len=%s",
        response.get("intent"),
        len(response.get("assistantMessage") or ""),
    )
    return response
