"""Gemini function declarations from Pydantic arg models. No LangChain."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _is_schema_title(key: str, value: Any) -> bool:
    """JSON Schema `title` is a string. A property named title is an object schema."""
    return key == "title" and isinstance(value, str)


def gemini_schema(node: Any) -> Any:
    """Gemini function parameters: drop JSON Schema title/default, keep a property named title."""
    if isinstance(node, list):
        return [gemini_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    if "anyOf" in node:
        variants = [item for item in node["anyOf"] if item != {"type": "null"}]
        if len(variants) == 1:
            merged = {
                k: v
                for k, v in node.items()
                if k not in {"anyOf", "default"} and not _is_schema_title(k, v)
            }
            merged.update(variants[0])
            return gemini_schema(merged)
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in {"default", "$defs", "definitions"} or _is_schema_title(key, value):
            continue
        out[key] = gemini_schema(value)
    return out


def _resolve_refs(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_resolve_refs(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        name = str(node["$ref"]).rsplit("/", 1)[-1]
        return _resolve_refs(defs.get(name) or {}, defs)
    return {key: _resolve_refs(value, defs) for key, value in node.items() if key != "$defs"}


def declaration(name: str, description: str, model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.get("$defs") or {}
    params = gemini_schema(_resolve_refs(raw, defs))
    if params.get("type") != "object":
        params = {"type": "object", "properties": {}}
    return {
        "name": name,
        "description": description,
        "parameters": params,
    }
