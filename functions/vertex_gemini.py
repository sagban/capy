"""Gemini via Vertex AI (ADC). Bills GCP project credits — no AI Studio API key."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger("capy.vertex")

DEFAULT_PROJECT = "capy-dogfood"
DEFAULT_LOCATION = "us-central1"
# dogfood project currently exposes 2.5-flash in us-central1 (2.0-flash → 404).
DEFAULT_MODEL = "gemini-2.5-flash"


def _project_id() -> str:
    return (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or DEFAULT_PROJECT
    )


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


def generate_with_tools(
    *,
    system: str,
    user_content: str,
    tool_declarations: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
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
                )
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

            # Do NOT set response_mime_type with tools — Gemini rejects / hangs on that combo.
            result = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.2,
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


def generate_text(*, system: str, user_content: str) -> str:
    """Short text completion with no tools. Empty string on failure."""
    try:
        from google.genai import types

        client = get_vertex_client()
        result = client.models.generate_content(
            model=_model(),
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.2,
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
