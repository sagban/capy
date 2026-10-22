"""One interpret_meal HTTP turn. Graph nodes call these functions."""

from __future__ import annotations

from typing import Any

from agent.llm.model import generate
from agent.harness.format import format_message
from agent.harness.execute import run_calls
from agent.harness.memory.assemble import build_pack
from agent.harness.outcomes import OutcomeError, normalize_outcome
from agent.harness.messaging import sanitize_assistant_message
from agent.harness.prompts import turn_prompt
from agent.harness.tool_args import validate_calls
from agent.tools.registry import TOOL_DECLARATIONS
from schemas import InterpretMealRequest, MealIntent, request_from_dict

MAX_TOOL_ROUNDS = 12


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
        "tool_trace": [],
        "rounds": 0,
    }


def _read_model(result: dict[str, Any]) -> dict[str, Any]:
    kind = result.get("kind")
    if kind == "error":
        return {"kind": "error", "message": result.get("message") or "unavailable"}
    if kind == "tool_calls":
        calls = list(result.get("calls") or [])
        text = str(result.get("text") or "")
        err = validate_calls(calls)
        if err:
            return {"kind": "bad_args", "message": err, "text": text}
        return {"kind": "tool_calls", "calls": calls, "text": text}
    return {"kind": "text", "text": str(result.get("text") or "")}


def call_model(state: dict[str, Any]) -> dict[str, Any]:
    req = InterpretMealRequest.model_validate(state["req"])
    context_pack = state.get("context_pack") or ""
    attempts = 0
    infra = 0
    validation_error = ""
    last_text = ""
    while attempts < 2:
        attempts += 1
        packed = turn_prompt(
            req,
            context_pack,
            validation_error=validation_error,
            tool_trace=list(state.get("tool_trace") or []),
        )
        result = _read_model(generate(
            packed["system"],
            packed["user"],
            packed["history"],
            tools=TOOL_DECLARATIONS,
            tool_exchange=packed["tool_exchange"],
            temperature=packed["temperature"],
        ))
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
        previous = str(state.get("model_text") or "")
        if result.get("kind") == "tool_calls":
            text = str(result.get("text") or "") or previous
            return {
                "calls": list(result.get("calls") or []),
                "model_text": text,
            }
        text = str(result.get("text") or "") or previous
        existing = state.get("outcome") or {}
        if existing.get("intent"):
            return {"calls": [], "model_text": text}
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
        prior = list(state.get("tool_trace") or [])
        trace, outcome = run_calls(
            req,
            calls,
            uid=state.get("uid"),
            trace=prior,
        )
        round_index = int(state.get("rounds") or 0) + 1
        for step in trace[len(prior) :]:
            step["round"] = round_index
    except Exception as exc:  # noqa: BLE001
        return {"outcome": empty_chat_outcome(model_text=str(state.get("model_text") or ""))}
    return {
        "tool_trace": trace,
        "outcome": outcome,
        "rounds": int(state.get("rounds") or 0) + 1,
        "calls": [],
    }


def format_reply(state: dict[str, Any]) -> dict[str, Any]:
    outcome = dict(state.get("outcome") or {})
    if "agent_unavailable" in (outcome.get("warnings") or []):
        return {"outcome": outcome}
    from agent.harness.save_memory import proposals_for_utterance
    from schemas import InterpretMealRequest

    req = InterpretMealRequest.model_validate(state["req"])
    extra = [item.model_dump(mode="json") for item in proposals_for_utterance(req)]
    facts = dict(outcome.get("phraseFacts") or {})
    if extra:
        outcome["memoryProposals"] = list(outcome.get("memoryProposals") or []) + extra
        facts["memory"] = list(facts.get("memory") or []) + extra
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
