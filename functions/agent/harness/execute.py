"""Run one batch of tool calls. Binds uid, library, and diary. Returns data to the model."""

from __future__ import annotations

from typing import Any

from agent.harness.diets import annotate_lookup
from agent.harness.outcomes import outcome_from_trace
from agent.harness.policy import gate_write
from agent.harness.tool_args import parse_tool_args
from agent.tools.diary_io import get_diary
from schemas import InterpretMealRequest


def _diary_slice(req: InterpretMealRequest, day_key: str) -> tuple[list[Any], dict[str, Any]]:
    key = (day_key or "").strip()
    remaining = req.diaryContext.remaining.model_dump(mode="json")
    if not key or key == (req.dayKey or "").strip():
        return list(req.diaryContext.today or []), remaining
    for day in req.diaryContext.previousDays or []:
        if (day.dayKey or "").strip() == key:
            return list(day.entries or []), remaining
    return [], remaining


def _bind(name: str, req: InterpretMealRequest, uid: str | None, arguments: dict[str, Any]) -> dict[str, Any]:
    bound = dict(arguments)
    if name == "search_library":
        bound["items"] = list(req.libraryContext or [])
    elif name == "get_diary":
        entries, remaining = _diary_slice(req, str(arguments.get("day_key") or ""))
        viewed = get_diary(str(arguments.get("day_key") or req.dayKey), entries, remaining)
        bound["entries"] = viewed["entries"]
        bound["remaining"] = viewed["remaining"]
    elif name in {"write_food_entry", "delete_food_entry"}:
        bound["uid"] = uid
    return bound


def run_calls(
    req: InterpretMealRequest,
    calls: list[dict[str, Any]],
    *,
    uid: str | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import phoenix_tracing

    carried = list(trace or [])
    for call in calls:
        name = str(call.get("name") or "")
        parsed = parse_tool_args(name, call.get("arguments") or {})
        if isinstance(parsed, str):
            result: dict[str, Any] = {"error": "bad_args", "message": parsed}
            carried.append({"name": name, "arguments": call.get("arguments") or {}, "result": result})
            continue
        spec, arguments = parsed
        gated = gate_write(name, arguments, req, uid)
        with phoenix_tracing.tool_span(name or "tool", arguments=arguments) as span:
            if gated is not None:
                result = gated
            else:
                payload = _bind(name, req, uid, arguments)
                try:
                    result = spec.fn(**payload)
                except TypeError as exc:
                    result = {"error": "bad_args", "message": str(exc)}
            if isinstance(result, dict):
                result = annotate_lookup(name, result, req)
            phoenix_tracing.set_output(span, {"tool": name})
        carried.append({"name": name, "arguments": arguments, "result": result})
    return carried, outcome_from_trace(req, carried)
