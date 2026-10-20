"""Merge one turn of tool calls into a single outcome."""

from __future__ import annotations

from typing import Any, Optional

from agent.harness.tools.common import blank_memory, chat
from schemas import InterpretMealRequest, MemoryProposal, WorkingMemory

def run_calls(req: InterpretMealRequest, calls: list[dict[str, Any]]) -> dict[str, Any]:
    import phoenix_tracing
    from agent.harness.tools.registry import parse_tool_args

    memory = blank_memory(req)
    ctx: dict[str, Any] = {"memory": memory, "proposals": []}
    primary: Optional[dict[str, Any]] = None
    suggestions: Optional[dict[str, Any]] = None
    for call in calls:
        name = str(call.get("name") or "")
        parsed = parse_tool_args(name, call.get("arguments") or {})
        if isinstance(parsed, str):
            return {"error": "bad_args", "message": parsed}
        tool, arguments = parsed
        with phoenix_tracing.tool_span(name or "tool", arguments=arguments) as span:
            result = tool.invoke({**arguments, "ctx": {**ctx, "req": req}})
            summary = phoenix_tracing.tool_result_summary(name or "tool", result)
            phoenix_tracing.set_output(span, summary)
            phoenix_tracing.set_attrs(
                span,
                {
                    "capy.tool": name,
                    "capy.intent": summary.get("intent"),
                    "capy.pending": summary.get("pending"),
                    "capy.option_count": summary.get("optionCount"),
                    "capy.dropped": summary.get("dropped"),
                    "capy.reason": summary.get("reason") or summary.get("pendingReason"),
                },
            )
        kind = (tool.metadata or {}).get("kind")
        if kind == "memory":
            if isinstance(result, dict) and result.get("error"):
                return result
            continue
        if isinstance(result, dict) and result.get("error"):
            return result
        if kind == "suggestions":
            suggestions = result
        else:
            primary = result

    proposals: list[MemoryProposal] = ctx["proposals"]
    if primary and primary.get("error"):
        return primary
    if suggestions and suggestions.get("error"):
        return suggestions
    if primary and suggestions:
        merged = dict(primary)
        merged["suggestionOptions"] = suggestions.get("suggestionOptions") or []
        merged["suggestionBudget"] = suggestions.get("suggestionBudget")
        facts = dict(merged.get("phraseFacts") or {})
        facts["suggestions"] = (suggestions.get("phraseFacts") or {}).get("options")
        merged["phraseFacts"] = facts
        wm = WorkingMemory.model_validate(merged["workingMemory"])
        other = WorkingMemory.model_validate(suggestions["workingMemory"])
        wm.lastSuggestionOptions = other.lastSuggestionOptions
        merged["workingMemory"] = wm.model_dump(mode="json")
        if proposals:
            merged["memoryProposals"] = [p.model_dump(mode="json") for p in proposals]
        return merged
    if primary:
        if proposals and not primary.get("memoryProposals"):
            primary["memoryProposals"] = [p.model_dump(mode="json") for p in proposals]
        return primary
    if suggestions:
        if proposals and not suggestions.get("memoryProposals"):
            suggestions["memoryProposals"] = [p.model_dump(mode="json") for p in proposals]
        return suggestions
    if proposals:
        return chat(req, memory, {"memory": [p.model_dump(mode="json") for p in proposals]}, proposals=proposals)
    return chat(req, memory, {"reason": "no tool result"})
