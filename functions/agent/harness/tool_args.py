"""Check model tool-call arguments against the registry. Not a tool itself."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from agent.tools.registry import TOOLS, ToolSpec


def parse_tool_args(name: str, arguments: dict[str, Any]) -> tuple[ToolSpec, dict[str, Any]] | str:
    spec = TOOLS.get(name)
    if spec is None:
        return f"unknown tool {name}"
    try:
        parsed = spec.args_model.model_validate(arguments or {})
    except ValidationError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return str(exc)
    payload = parsed.model_dump() if isinstance(parsed, BaseModel) else dict(parsed)
    return spec, payload


def validate_calls(calls: list[dict[str, Any]]) -> str | None:
    if not calls:
        return None
    for call in calls:
        parsed = parse_tool_args(str(call.get("name") or ""), call.get("arguments") or {})
        if isinstance(parsed, str):
            return parsed
    return None
