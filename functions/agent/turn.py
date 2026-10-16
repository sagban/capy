"""One interpret_meal HTTP turn. Graph nodes call these functions."""

from __future__ import annotations

from typing import Any

from agent.llm import model_turn
from agent.harness.format import format_message
from agent.harness.tools.jobs import run_calls
from agent.harness.memory.assemble import build_pack
from agent.harness.outcomes import OutcomeError, normalize_outcome
from agent.harness.messaging import sanitize_assistant_message
from schemas import InterpretMealRequest, MealIntent, request_from_dict


def unavailable(warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "intent": MealIntent.unknown.value,
        "candidates": [],
        "assistantMessage": "",
        "warnings": warnings or ["agent_unavailable"],
        "memoryProposals": [],
        "pendingAction": None,
        "suggestionOptions": [],
    }


def empty_chat_outcome(*, model_text: str = "") -> dict[str, Any]:
    return {
        "intent": MealIntent.unknown.value,
        "candidates": [],
        "assistantMessage": "",
        "warnings": [],
        "memoryProposals": [],
        "pendingAction": None,
        "suggestionOptions": [],
        "phraseFacts": {"chat": True},
        "_model_text": model_text,
    }


def prepare(request: dict[str, Any]) -> dict[str, Any]:
    req = request_from_dict(request)
    return {
        "req": req.model_dump(mode="json"),
        "context_pack": build_pack(req),
        "calls": [],
        "model_text": "",
        "outcome": {},
        "response": {},
    }


def call_model(state: dict[str, Any]) -> dict[str, Any]:
    req = InterpretMealRequest.model_validate(state["req"])
    context_pack = state.get("context_pack") or ""
    attempts = 0
    infra = 0
    validation_error = ""
    last_text = ""
    while attempts < 2:
        attempts += 1
        result = model_turn(
            req,
            context_pack,
            validation_error=validation_error,
        )
        if result.get("kind") == "error":
            infra += 1
            if infra >= 2:
                return {"outcome": unavailable(), "calls": [], "model_text": ""}
            continue
        if result.get("kind") == "bad_args":
            last_text = str(result.get("text") or "")
            if attempts >= 2:
                return {
                    "calls": [],
                    "model_text": last_text,
                    "outcome": empty_chat_outcome(model_text=last_text),
                }
            validation_error = str(result.get("message") or "bad arguments")
            continue
        if result.get("kind") == "tool_calls":
            return {
                "calls": list(result.get("calls") or []),
                "model_text": str(result.get("text") or ""),
                "outcome": {},
            }
        text = str(result.get("text") or "")
        return {
            "calls": [],
            "model_text": text,
            "outcome": empty_chat_outcome(model_text=text),
        }
    return {"outcome": unavailable(), "calls": [], "model_text": ""}


def run_environment(state: dict[str, Any]) -> dict[str, Any]:
    req = InterpretMealRequest.model_validate(state["req"])
    calls = list(state.get("calls") or [])
    if not calls:
        return {"outcome": empty_chat_outcome(model_text=str(state.get("model_text") or ""))}
    try:
        outcome = run_calls(req, calls)
    except Exception as exc:  # noqa: BLE001
        outcome = {"error": "bad_args", "message": str(exc)}
    if outcome.get("error") == "bad_args":
        return {"outcome": empty_chat_outcome(model_text=str(state.get("model_text") or ""))}
    return {"outcome": outcome}


def format_reply(state: dict[str, Any]) -> dict[str, Any]:
    outcome = dict(state.get("outcome") or {})
    if "agent_unavailable" in (outcome.get("warnings") or []):
        return {"outcome": outcome}
    facts = outcome.get("phraseFacts") or {}
    draft = state.get("model_text") or outcome.pop("_model_text", "") or ""
    message = format_message(draft=draft, outcome=facts)
    outcome["assistantMessage"] = message
    outcome.pop("phraseFacts", None)
    outcome.pop("_model_text", None)
    return {"outcome": outcome}


def finalize(state: dict[str, Any]) -> dict[str, Any]:
    outcome = dict(state.get("outcome") or {})
    if not outcome:
        payload = unavailable()
    else:
        outcome.pop("phraseFacts", None)
        outcome.pop("_model_text", None)
        outcome["assistantMessage"] = sanitize_assistant_message(
            outcome.get("assistantMessage"),
            allow_empty=True,
        )
        try:
            payload = normalize_outcome(outcome)
        except (OutcomeError, Exception):  # noqa: BLE001
            payload = unavailable(["agent_unavailable", "outcome_invalid"])
    try:
        from schemas import InterpretMealResponse

        payload = InterpretMealResponse.model_validate(payload).model_dump(mode="json")
    except Exception:  # noqa: BLE001
        payload = unavailable(["agent_unavailable", "outcome_invalid"])
    return {"response": payload}
