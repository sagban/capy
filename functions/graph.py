"""LangGraph-style meal intent graph.

Uses Gemini when GEMINI_API_KEY is set; otherwise deterministic heuristics for
emulator goldens and local tests. Never emits trusted calorie/PCF totals.
"""

from __future__ import annotations

import re
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from schemas import (
    FoodCandidate,
    InterpretMealRequest,
    InterpretMealResponse,
    MealIntent,
    MemoryProposal,
)
from tools import run_tool


class GraphState(TypedDict, total=False):
    request: dict[str, Any]
    intent: str
    tool_results: dict[str, Any]
    candidates: list[dict[str, Any]]
    clarifying_question: Optional[str]
    assistant_message: str
    warnings: list[str]
    memory_proposals: list[dict[str, Any]]
    suggested_template_id: Optional[str]
    response: dict[str, Any]


MEMORY_HINTS = re.compile(
    r"\b(remember|forget|i (usually|don't|do not|always|never)|no microwave|train(?:s|ing)?)\b",
    re.I,
)
FORGET_HINTS = re.compile(r"\bforget\b", re.I)
SUGGEST_HINTS = re.compile(r"\b(suggest|what should i eat|idea for)\b", re.I)
LOG_HINTS = re.compile(r"\b(had|ate|log|logged|for (lunch|dinner|breakfast))\b", re.I)
PORTION_AMBIGUOUS = re.compile(r"\b(some|a bit|helping|plate of)\b", re.I)


def _parse_request(state: GraphState) -> InterpretMealRequest:
    from schemas import request_from_dict

    return request_from_dict(state["request"])


def interpret_intent(state: GraphState) -> GraphState:
    req = _parse_request(state)
    text = req.utterance.strip()
    wm = req.conversation.workingMemory

    # Follow-up on clarify uses working memory
    if wm and wm.pendingIntent == "clarify" and text:
        intent = MealIntent.log_meal
        warnings: list[str] = []
    elif FORGET_HINTS.search(text) or (
        MEMORY_HINTS.search(text) and "forget" in text.lower()
    ):
        intent = MealIntent.update_memory
        warnings = []
    elif MEMORY_HINTS.search(text) and not LOG_HINTS.search(text):
        intent = MealIntent.update_memory
        warnings = []
    elif SUGGEST_HINTS.search(text):
        intent = MealIntent.suggest_meal
        warnings = []
    elif PORTION_AMBIGUOUS.search(text) and not wm:
        intent = MealIntent.clarify
        warnings = ["ambiguous_portion"]
    elif LOG_HINTS.search(text) or text:
        intent = MealIntent.log_meal
        warnings = []
    else:
        intent = MealIntent.unknown
        warnings = []

    # Optional Gemini refinement
    gemini_intent = _gemini_intent(req)
    if gemini_intent:
        intent = gemini_intent

    return {
        **state,
        "intent": intent.value,
        "warnings": warnings,
        "tool_results": {},
        "candidates": [],
        "memory_proposals": [],
    }


def tool_router(state: GraphState) -> GraphState:
    req = _parse_request(state)
    intent = MealIntent(state.get("intent", "unknown"))
    results: dict[str, Any] = {}

    results["prefs"] = run_tool("get_user_preferences", req)
    results["diet"] = run_tool("get_dietary_restrictions", req)
    results["ltm"] = run_tool("get_long_term_memory", req)

    if intent in {MealIntent.log_meal, MealIntent.correct_meal, MealIntent.clarify}:
        results["today"] = run_tool("get_today_food_log", req)
        # Extract a search term from utterance
        query = _food_query(req.utterance)
        if query:
            results["search"] = run_tool("search_food", req, query=query, limit=8)
    if intent == MealIntent.suggest_meal:
        results["today"] = run_tool("get_today_food_log", req)
        results["previous"] = run_tool("get_previous_food_logs", req)
        results["propose"] = run_tool("propose_meal", req)

    return {**state, "tool_results": results}


def resolve_and_emit(state: GraphState) -> GraphState:
    req = _parse_request(state)
    intent = MealIntent(state.get("intent", "unknown"))
    tools = state.get("tool_results") or {}
    warnings = list(state.get("warnings") or [])
    candidates: list[FoodCandidate] = []
    clarifying: Optional[str] = None
    memory_proposals: list[MemoryProposal] = []
    suggested_template_id: Optional[str] = None
    message = ""

    wm = req.conversation.workingMemory
    if wm and wm.pendingIntent == "clarify" and intent == MealIntent.log_meal:
        # Apply follow-up to prior candidates
        grams = _parse_grams(req.utterance)
        for c in wm.candidates:
            candidates.append(
                FoodCandidate(
                    foodId=c.foodId,
                    displayName=c.displayName,
                    grams=grams if grams is not None else c.grams,
                    confidence=0.8,
                )
            )
        message = "got it — confirm portions?"
        intent = MealIntent.log_meal
    elif intent == MealIntent.clarify:
        clarifying = "Was that about a cup, or half?"
        message = "quick check on the portion"
        search = tools.get("search") or {}
        for hit in (search.get("results") or [])[:2]:
            candidates.append(
                FoodCandidate(
                    foodId=hit["foodId"],
                    displayName=hit["displayName"],
                    grams=None,
                    confidence=0.55,
                )
            )
    elif intent == MealIntent.suggest_meal:
        propose = tools.get("propose") or {}
        proposals = propose.get("proposals") or []
        if not proposals:
            message = "nothing that fits cleanly — try logging what you have"
            warnings.append("abstain_no_proposal")
            intent = MealIntent.unknown
        else:
            top = proposals[0]
            suggested_template_id = top.get("templateId")
            for item in top.get("items") or []:
                candidates.append(FoodCandidate(**item))
            message = f"fits remaining: {top.get('name')}"
    elif intent == MealIntent.update_memory:
        text = req.utterance.strip()
        if FORGET_HINTS.search(text):
            # Match against LTM notes
            notes = (tools.get("ltm") or {}).get("notes") or []
            deleted = False
            for note in notes:
                if any(
                    token in note["text"].lower()
                    for token in _forget_tokens(text)
                    if len(token) > 3
                ):
                    memory_proposals.append(
                        MemoryProposal(action="delete", id=note["id"])
                    )
                    deleted = True
            message = "removed that from memory" if deleted else "nothing matching to forget"
        else:
            fact = _memory_fact(text)
            memory_proposals.append(MemoryProposal(action="add", text=fact))
            message = "saved that for later"
    elif intent == MealIntent.log_meal:
        search = tools.get("search") or {}
        hits = search.get("results") or []
        if not hits:
            # Try broader search tokens
            for token in _tokens(req.utterance):
                search = run_tool("search_food", req, query=token, limit=5)
                hits = search.get("results") or []
                if hits:
                    break
        if not hits:
            clarifying = "which food was that?"
            intent = MealIntent.clarify
            message = "need a clearer food name"
            warnings.append("no_catalog_hit")
        else:
            grams = _parse_grams(req.utterance)
            if grams is None and PORTION_AMBIGUOUS.search(req.utterance):
                clarifying = "Was that about a cup, or half?"
                intent = MealIntent.clarify
                message = "quick check on the portion"
                warnings.append("ambiguous_portion")
                for hit in hits[:1]:
                    candidates.append(
                        FoodCandidate(
                            foodId=hit["foodId"],
                            displayName=hit["displayName"],
                            grams=None,
                            confidence=0.6,
                        )
                    )
            else:
                for hit in hits[:3]:
                    candidates.append(
                        FoodCandidate(
                            foodId=hit["foodId"],
                            displayName=hit["displayName"],
                            grams=grams if grams is not None else 150,
                            confidence=0.75,
                        )
                    )
                message = "logged — confirm portions?"
    else:
        message = "not sure what to do with that"

    # Diet hard-filter on candidates
    diets = {d.lower() for d in ((tools.get("diet") or {}).get("diets") or [])}
    if "vegetarian" in diets or "vegan" in diets:
        from catalog import get_food
        from tools import _diet_blocks_food

        filtered = []
        for c in candidates:
            food = get_food(c.foodId)
            if food and _diet_blocks_food(food, diets):
                warnings.append("filtered_diet")
                continue
            if any(token in c.displayName.lower() for token in ("chicken", "salmon", "beef", "pork")):
                warnings.append("filtered_diet")
                continue
            filtered.append(c)
        candidates = filtered

    response = InterpretMealResponse(
        intent=intent,
        candidates=candidates,
        clarifyingQuestion=clarifying,
        suggestedTemplateId=suggested_template_id,
        assistantMessage=message,
        warnings=warnings,
        memoryProposals=memory_proposals,
    )
    return {
        **state,
        "intent": intent.value,
        "candidates": [c.model_dump() for c in candidates],
        "clarifying_question": clarifying,
        "assistant_message": message,
        "warnings": warnings,
        "memory_proposals": [m.model_dump() for m in memory_proposals],
        "suggested_template_id": suggested_template_id,
        "response": response.model_dump(mode="json"),
    }


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("interpret_intent", interpret_intent)
    g.add_node("tool_router", tool_router)
    g.add_node("resolve_and_emit", resolve_and_emit)
    g.add_edge(START, "interpret_intent")
    g.add_edge("interpret_intent", "tool_router")
    g.add_edge("tool_router", "resolve_and_emit")
    g.add_edge("resolve_and_emit", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_interpret(payload: dict[str, Any]) -> dict[str, Any]:
    graph = get_graph()
    final = graph.invoke({"request": payload})
    return final.get("response") or {
        "intent": "unknown",
        "candidates": [],
        "assistantMessage": "empty response",
        "warnings": ["empty_graph"],
    }


def _food_query(utterance: str) -> str:
    cleaned = re.sub(
        r"\b(i|had|ate|for|lunch|dinner|breakfast|snack|some|a|an|the|and|with)\b",
        " ",
        utterance.lower(),
    )
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return " ".join(cleaned.split())


def _tokens(utterance: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", utterance.lower()) if len(t) > 2]


def _parse_grams(utterance: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*g\b", utterance.lower())
    if m:
        return float(m.group(1))
    if re.search(r"\bhalf\b", utterance.lower()):
        return 75.0
    if re.search(r"\bcup\b", utterance.lower()):
        return 150.0
    return None


def _memory_fact(utterance: str) -> str:
    text = utterance.strip()
    text = re.sub(r"^(please\s+)?remember\s+(that\s+)?", "", text, flags=re.I)
    return text[:240]


def _forget_tokens(utterance: str) -> list[str]:
    text = re.sub(r"\b(forget|that|the|please|i|said|about)\b", " ", utterance.lower())
    return [t for t in text.split() if t]


def _gemini_intent(req: InterpretMealRequest) -> Optional[MealIntent]:
    """Vertex AI Gemini (ADC). No AI Studio API key."""
    from vertex_gemini import classify_intent

    return classify_intent(req)
