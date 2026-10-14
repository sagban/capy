"""Six-node meal graph: ingest, dispatch, model_turn, execute, phrase, respond."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agent import model_turn
from harness.context import compact_context_pack
from harness.execute import run_calls
from harness.outcomes import OutcomeError, normalize_outcome
from harness.phrase import phrase_message
from messaging import sanitize_assistant_message
from schemas import InterpretMealRequest, InterpretMealResponse, MealIntent, request_from_dict


class GraphState(TypedDict, total=False):
    request: dict[str, Any]
    req: dict[str, Any]
    context_pack: str
    route: str
    calls: list[dict[str, Any]]
    model_text: str
    validation_error: str
    prior_text: str
    model_attempts: int
    infra_attempts: int
    outcome: dict[str, Any]
    response: dict[str, Any]


def _unavailable(warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "intent": MealIntent.unknown.value,
        "candidates": [],
        "assistantMessage": "",
        "warnings": warnings or ["agent_unavailable"],
        "memoryProposals": [],
        "pendingAction": None,
        "suggestionOptions": [],
    }


def ingest(state: GraphState) -> GraphState:
    req = request_from_dict(state["request"])
    return {
        "req": req.model_dump(mode="json"),
        "context_pack": compact_context_pack(req),
        "model_attempts": 0,
        "infra_attempts": 0,
        "validation_error": "",
    }


def dispatch(state: GraphState) -> GraphState:
    req = InterpretMealRequest.model_validate(state["req"])
    if req.action is not None:
        return {
            "route": "execute",
            "calls": [{"name": "_action", "arguments": req.action.model_dump(mode="json")}],
        }
    return {"route": "model_turn", "calls": []}


def model_node(state: GraphState) -> GraphState:
    req = InterpretMealRequest.model_validate(state["req"])
    attempts = int(state.get("model_attempts") or 0) + 1
    result = model_turn(
        req,
        state.get("context_pack") or "",
        validation_error=state.get("validation_error") or "",
        prior_text=state.get("prior_text") or "",
    )
    if result.get("kind") == "error":
        infra = int(state.get("infra_attempts") or 0) + 1
        return {
            "model_attempts": attempts,
            "infra_attempts": infra,
            "route": "respond" if infra >= 2 else "model_turn",
            "outcome": _unavailable() if infra >= 2 else {},
        }
    if result.get("kind") == "bad_args":
        if attempts >= 2:
            return {
                "model_attempts": attempts,
                "route": "phrase",
                "model_text": str(result.get("text") or ""),
                "validation_error": "",
                "outcome": {
                    "intent": MealIntent.unknown.value,
                    "candidates": [],
                    "assistantMessage": "",
                    "warnings": [],
                    "memoryProposals": [],
                    "pendingAction": None,
                    "suggestionOptions": [],
                    "phraseFacts": {"chat": True},
                },
            }
        return {
            "model_attempts": attempts,
            "route": "model_turn",
            "validation_error": str(result.get("message") or "bad arguments"),
        }
    if result.get("kind") == "tool_calls":
        return {
            "model_attempts": attempts,
            "route": "execute",
            "calls": list(result.get("calls") or []),
            "model_text": str(result.get("text") or ""),
            "validation_error": "",
        }
    return {
        "model_attempts": attempts,
        "route": "phrase",
        "model_text": str(result.get("text") or ""),
        "calls": [],
        "outcome": {
            "intent": MealIntent.unknown.value,
            "candidates": [],
            "assistantMessage": "",
            "warnings": [],
            "memoryProposals": [],
            "pendingAction": None,
            "suggestionOptions": [],
            "phraseFacts": {"chat": True},
        },
    }


def execute_node(state: GraphState) -> GraphState:
    req = InterpretMealRequest.model_validate(state["req"])
    calls = list(state.get("calls") or [])
    if not calls:
        return {
            "route": "phrase",
            "outcome": {
                "intent": MealIntent.unknown.value,
                "candidates": [],
                "assistantMessage": "",
                "warnings": [],
                "memoryProposals": [],
                "pendingAction": None,
                "suggestionOptions": [],
                "phraseFacts": {"chat": True},
            },
        }
    try:
        outcome = run_calls(req, calls)
    except Exception as exc:  # noqa: BLE001
        outcome = {"error": "bad_args", "message": str(exc)}
    if outcome.get("error") == "bad_args":
        return {
            "route": "phrase",
            "validation_error": "",
            "outcome": {
                "intent": MealIntent.unknown.value,
                "candidates": [],
                "assistantMessage": "",
                "warnings": [],
                "memoryProposals": [],
                "pendingAction": None,
                "suggestionOptions": [],
                "phraseFacts": {"chat": True},
            },
        }
    return {"route": "phrase", "outcome": outcome, "validation_error": ""}


def phrase_node(state: GraphState) -> GraphState:
    outcome = dict(state.get("outcome") or {})
    if "agent_unavailable" in (outcome.get("warnings") or []):
        return {"outcome": outcome}
    req = InterpretMealRequest.model_validate(state["req"])
    facts = outcome.get("phraseFacts") or {}
    draft = state.get("model_text") or ""
    message = phrase_message(
        draft=draft,
        outcome=facts,
        context_pack=state.get("context_pack") or "",
        user_text=req.utterance,
        generate=None,
    )
    outcome["assistantMessage"] = message
    outcome.pop("phraseFacts", None)
    return {"outcome": outcome}


def respond(state: GraphState) -> GraphState:
    outcome = dict(state.get("outcome") or {})
    if not outcome:
        payload = _unavailable()
    else:
        outcome.pop("phraseFacts", None)
        outcome["assistantMessage"] = sanitize_assistant_message(
            outcome.get("assistantMessage"),
            allow_empty=True,
        )
        try:
            payload = normalize_outcome(outcome)
        except (OutcomeError, Exception):  # noqa: BLE001
            payload = _unavailable(["agent_unavailable", "outcome_invalid"])
    try:
        payload = InterpretMealResponse.model_validate(payload).model_dump(mode="json")
    except Exception:  # noqa: BLE001
        payload = _unavailable(["agent_unavailable", "outcome_invalid"])
    return {"response": payload, "warnings": payload.get("warnings") or []}


def _after_dispatch(state: GraphState) -> str:
    return "execute" if state.get("route") == "execute" else "model_turn"


def _after_model(state: GraphState) -> str:
    return str(state.get("route") or "phrase")


def _after_execute(state: GraphState) -> str:
    if state.get("route") == "model_turn":
        return "model_turn"
    return "phrase"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("ingest", ingest)
    graph.add_node("dispatch", dispatch)
    graph.add_node("model_turn", model_node)
    graph.add_node("execute", execute_node)
    graph.add_node("phrase", phrase_node)
    graph.add_node("respond", respond)
    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "dispatch")
    graph.add_conditional_edges("dispatch", _after_dispatch, {"execute": "execute", "model_turn": "model_turn"})
    graph.add_conditional_edges(
        "model_turn",
        _after_model,
        {"execute": "execute", "model_turn": "model_turn", "phrase": "phrase", "respond": "respond"},
    )
    graph.add_conditional_edges(
        "execute",
        _after_execute,
        {"model_turn": "model_turn", "phrase": "phrase"},
    )
    graph.add_edge("phrase", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def reset_graph() -> None:
    global _GRAPH
    _GRAPH = None


def run_interpret(payload: dict[str, Any]) -> dict[str, Any]:
    final = get_graph().invoke({"request": payload})
    response = final.get("response")
    if isinstance(response, dict) and response.get("intent"):
        return response
    return _unavailable()
