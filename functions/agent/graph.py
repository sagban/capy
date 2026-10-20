"""Thin LangGraph: prepare → llm → environment → format → respond."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

import phoenix_tracing
from agent.harness.checkpointer import get_checkpointer, reset_checkpointer
from agent.harness.memory.episodic import thread_id as conversation_thread_id
from schemas import request_from_dict
from agent.turn import (
    call_model,
    finalize,
    format_reply,
    prepare,
    run_environment,
    unavailable,
)


class GraphState(TypedDict, total=False):
    req: dict[str, Any]
    context_pack: str
    calls: list[dict[str, Any]]
    model_text: str
    outcome: dict[str, Any]
    response: dict[str, Any]


def prepare_node(state: GraphState) -> GraphState:
    with phoenix_tracing.chain_span("prepare") as span:
        out = prepare(state["req"])
        phoenix_tracing.set_output(
            span,
            {"threadId": ((out.get("req") or {}).get("conversation") or {}).get("threadId")},
        )
        return out


def llm_node(state: GraphState) -> GraphState:
    with phoenix_tracing.chain_span("llm") as span:
        out = call_model(dict(state))
        phoenix_tracing.set_output(
            span,
            {"calls": [c.get("name") for c in (out.get("calls") or [])]},
        )
        return out


def environment_node(state: GraphState) -> GraphState:
    calls = list(state.get("calls") or [])
    tool_names = [str(c.get("name") or "?").strip() or "?" for c in calls]
    # Phoenix: show tool name(s) instead of the opaque graph node label.
    span_name = "+".join(tool_names) if tool_names else "environment"
    with phoenix_tracing.chain_span(span_name) as span:
        out = run_environment(dict(state))
        outcome = out.get("outcome") or {}
        summary = {
            "tools": tool_names,
            "intent": outcome.get("intent"),
            "reason": (outcome.get("phraseFacts") or {}).get("reason"),
            "dropped": (outcome.get("phraseFacts") or {}).get("dropped"),
            "optionCount": len(outcome.get("suggestionOptions") or []),
            "pending": (outcome.get("pendingAction") or {}).get("type")
            if isinstance(outcome.get("pendingAction"), dict)
            else None,
        }
        phoenix_tracing.set_output(span, summary)
        phoenix_tracing.set_attrs(
            span,
            {
                "capy.tools": tool_names,
                "capy.intent": summary.get("intent"),
                "capy.dropped": summary.get("dropped"),
                "capy.option_count": summary.get("optionCount"),
                "capy.pending": summary.get("pending"),
            },
        )
        return out


def format_node(state: GraphState) -> GraphState:
    with phoenix_tracing.chain_span("format") as span:
        out = format_reply(dict(state))
        phoenix_tracing.set_output(
            span,
            {"len": len((out.get("outcome") or {}).get("assistantMessage") or "")},
        )
        return out


def respond_node(state: GraphState) -> GraphState:
    return finalize(dict(state))


def _after_llm(state: GraphState) -> str:
    outcome = state.get("outcome") or {}
    if "agent_unavailable" in (outcome.get("warnings") or []):
        return "respond"
    if state.get("calls"):
        return "environment"
    return "format"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("llm", llm_node)
    graph.add_node("environment", environment_node)
    graph.add_node("format", format_node)
    graph.add_node("respond", respond_node)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "llm")
    graph.add_conditional_edges(
        "llm",
        _after_llm,
        {"environment": "environment", "format": "format", "respond": "respond"},
    )
    graph.add_edge("environment", "format")
    graph.add_edge("format", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=get_checkpointer())


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def reset_graph() -> None:
    global _GRAPH
    _GRAPH = None
    reset_checkpointer()


def run_interpret(payload: dict[str, Any], *, uid: str = "test", thread_id: str | None = None) -> dict[str, Any]:
    req = request_from_dict(payload)
    tid = thread_id or conversation_thread_id(req)
    config = {"configurable": {"thread_id": f"{uid}:{tid}"}}
    final = get_graph().invoke({"req": req.model_dump(mode="json")}, config)
    response = final.get("response")
    if isinstance(response, dict) and response.get("intent"):
        return response
    return unavailable()
