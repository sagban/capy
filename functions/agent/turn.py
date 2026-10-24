"""One interpret_meal HTTP turn. Graph nodes call these functions."""

from __future__ import annotations

from typing import Any

from agent.llm.model import open_conversation
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


def _one_reply(convo: Any) -> dict[str, Any]:
    """One model reply, with the same two tries for a transport error or bad arguments."""
    attempts = 0
    infra = 0
    while attempts < 2:
        attempts += 1
        result = _read_model(convo.complete())
        if result.get("kind") == "error":
            infra += 1
            if infra >= 2:
                return {"stop": "unavailable"}
            continue
        if result.get("kind") == "bad_args":
            text = str(result.get("text") or "")
            if attempts >= 2:
                return {"stop": "bad_args", "text": text}
            convo.add_argument_error(str(result.get("message") or "bad arguments"))
            continue
        return result
    return {"stop": "unavailable"}


def run_agent(state: dict[str, Any]) -> dict[str, Any]:
    """One conversation. The model calls a tool or replies. The harness only runs that call."""
    req = InterpretMealRequest.model_validate(state["req"])
    packed = turn_prompt(req, state.get("context_pack") or "")
    convo = open_conversation(
        packed["system"],
        packed["user"],
        packed["history"],
        tools=TOOL_DECLARATIONS,
        temperature=packed["temperature"],
    )
    trace: list[dict[str, Any]] = []
    outcome: dict[str, Any] = {}
    model_text = ""
    rounds = 0
    while True:
        result = _one_reply(convo)
        if result.get("stop") == "unavailable":
            return {"outcome": unavailable(), "calls": [], "model_text": "", "tool_trace": trace, "rounds": rounds}
        if result.get("stop") == "bad_args":
            text = str(result.get("text") or "") or model_text
            return {
                "calls": [],
                "model_text": text,
                "outcome": empty_chat_outcome(model_text=text),
                "tool_trace": trace,
                "rounds": rounds,
            }
        text = str(result.get("text") or "") or model_text
        if text:
            model_text = text
        if result.get("kind") != "tool_calls":
            break
        if rounds >= MAX_TOOL_ROUNDS:
            break
        calls = list(result.get("calls") or [])
        try:
            prior = len(trace)
            trace, outcome = run_calls(req, calls, uid=state.get("uid"), trace=trace)
            rounds += 1
            for step in trace[prior:]:
                step["round"] = rounds
        except Exception:  # noqa: BLE001
            return {
                "outcome": empty_chat_outcome(model_text=model_text),
                "calls": [],
                "model_text": model_text,
                "tool_trace": trace,
                "rounds": rounds,
            }
        convo.add_tool_results(
            [{"name": step.get("name"), "result": step.get("result")} for step in trace[prior:]]
        )
    if not outcome.get("intent"):
        outcome = empty_chat_outcome(model_text=model_text)
    return {
        "outcome": outcome,
        "model_text": model_text,
        "tool_trace": trace,
        "calls": [],
        "rounds": rounds,
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
