"""Gemini via Vertex AI (ADC). Bills GCP project credits — no AI Studio API key."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger("capy.vertex")

# Gemini 3 publisher models are served from the Vertex `global` endpoint.
DEFAULT_LOCATION = "global"
# 3.x allows google_search + function_declarations on one turn; 2.5 does not.
DEFAULT_MODEL = "gemini-3.5-flash"


def _project_id() -> str:
    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or ""
    ).strip()
    if not project:
        raise RuntimeError("Set GOOGLE_CLOUD_PROJECT to your GCP project.")
    return project


def _location() -> str:
    return os.environ.get("GOOGLE_CLOUD_LOCATION") or DEFAULT_LOCATION


def _model() -> str:
    return os.environ.get("VERTEX_GEMINI_MODEL") or DEFAULT_MODEL


@lru_cache(maxsize=1)
def get_vertex_client():
    from google import genai

    return genai.Client(
        vertexai=True,
        project=_project_id(),
        location=_location(),
    )


def _append_tool_exchange(contents: list[Any], exchange: list[dict[str, Any]] | None, types: Any) -> None:
    for group in exchange or []:
        call_parts = []
        response_parts = []
        calls = list(group.get("calls") or [])
        results = list(group.get("results") or [])
        for call in calls:
            name = str(call.get("name") or "")
            if not name:
                continue
            arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            call_parts.append(types.Part.from_function_call(name=name, args=arguments))
        for item in results:
            name = str(item.get("name") or "")
            if not name:
                continue
            payload = item.get("result") if isinstance(item.get("result"), dict) else {"result": item.get("result")}
            response_parts.append(types.Part.from_function_response(name=name, response=payload))
        if call_parts:
            contents.append(types.Content(role="model", parts=call_parts))
        if response_parts:
            contents.append(types.Content(role="user", parts=response_parts))


def generate_with_tools(
    *,
    system: str,
    user_content: str,
    tool_declarations: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
    tool_exchange: list[dict[str, Any]] | None = None,
    temperature: float,
) -> dict[str, Any]:
    """
    One agent turn. Returns:
      {"kind": "tool_calls", "calls": [{"name", "arguments"}, ...], "text": str}
      {"kind": "text", "text": str}
      {"kind": "error", "message": str}
    """
    import phoenix_tracing

    model = _model()
    with phoenix_tracing.llm_span(
        "vertex_gemini",
        model=model,
        input_value=user_content[:4000],
    ) as span:
        try:
            from google.genai import types

            client = get_vertex_client()

            # Gemini 3+ (global): function tools + Google Search grounding on one turn.
            # Gemini 2.5 rejects that mix — keep VERTEX_GEMINI_MODEL on 3.x for search.
            tools = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=d["name"],
                            description=d.get("description") or "",
                            parameters=d.get("parameters") or {"type": "object", "properties": {}},
                        )
                        for d in tool_declarations
                    ]
                ),
                types.Tool(google_search=types.GoogleSearch()),
            ]

            contents: list[Any] = []
            for turn in history or []:
                role = turn.get("role") or "user"
                text = turn.get("text") or ""
                if text:
                    contents.append(
                        types.Content(
                            role=role if role in ("user", "model") else "user",
                            parts=[types.Part.from_text(text=text)],
                        )
                    )

            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=user_content)])
            )
            _append_tool_exchange(contents, tool_exchange, types)

            # Do NOT set response_mime_type with tools — Gemini rejects / hangs on that combo.
            result = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    tools=tools,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vertex_generate_failed: %s: %s", type(exc).__name__, exc)
            phoenix_tracing.set_output(
                span,
                {"kind": "error", "message": "unavailable", "error": f"{type(exc).__name__}: {exc}"[:500]},
            )
            return {"kind": "error", "message": "unavailable"}

        calls: list[dict[str, Any]] = []
        texts: list[str] = []
        try:
            candidates = getattr(result, "candidates", None) or []
            if candidates:
                parts = getattr(candidates[0].content, "parts", None) or []
                for part in parts:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        texts.append(str(part_text))
                    fc = getattr(part, "function_call", None)
                    if fc is None:
                        continue
                    name = getattr(fc, "name", None) or ""
                    args = dict(getattr(fc, "args", None) or {})
                    if name:
                        calls.append({"name": name, "arguments": args})
        except Exception:  # noqa: BLE001
            calls = []

        if calls:
            out = {"kind": "tool_calls", "calls": calls, "text": "\n".join(texts).strip()}
            phoenix_tracing.set_output(span, {"kind": "tool_calls", "calls": [c["name"] for c in calls]})
            return out

        text = "\n".join(texts).strip()
        if not text:
            try:
                text = (result.text or "").strip()
            except Exception:  # noqa: BLE001
                text = ""
        if text:
            out = {"kind": "text", "text": text[:800]}
            phoenix_tracing.set_output(span, out)
            return out
        phoenix_tracing.set_output(span, {"kind": "error", "message": "empty"})
        return {"kind": "error", "message": "empty"}


def generate_text(
    *,
    system: str,
    user_content: str,
    temperature: float,
) -> str:
    """Short text completion with no tools. Empty string on failure."""
    try:
        from google.genai import types

        client = get_vertex_client()
        result = client.models.generate_content(
            model=_model(),
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
            ),
        )
        return (result.text or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("vertex_text_failed: %s: %s", type(exc).__name__, exc)
        return ""


def _parse_json(text: str) -> Optional[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else None
            except Exception:  # noqa: BLE001
                return None
        return None
