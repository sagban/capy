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
DEFAULT_LIVE_LOCATION = "us-central1"
# 3.x allows google_search + function_declarations on one turn; 2.5 does not.
DEFAULT_MODEL = "gemini-3.5-flash"


def _project_id() -> str:
    project = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or os.environ.get("CAPY_PROJECT_ID")
        or ""
    ).strip()
    if not project:
        raise RuntimeError("Set GOOGLE_CLOUD_PROJECT to your GCP project.")
    return project


def _location() -> str:
    return os.environ.get("GOOGLE_CLOUD_LOCATION") or DEFAULT_LOCATION


def _live_location() -> str:
    loc = (os.environ.get("VERTEX_GEMINI_LIVE_LOCATION") or "").strip()
    if loc:
        return loc
    base = _location().strip()
    if base and base.lower() != "global":
        return base
    return DEFAULT_LIVE_LOCATION


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


@lru_cache(maxsize=1)
def get_vertex_live_client():
    from google import genai

    return genai.Client(
        vertexai=True,
        project=_project_id(),
        location=_live_location(),
    )


def _function_declaration(spec: dict[str, Any], types: Any) -> Any:
    name = str(spec.get("name") or "")
    description = spec.get("description") or ""
    schema = spec.get("parameters_json_schema")
    if isinstance(schema, dict):
        return types.FunctionDeclaration(
            name=name,
            description=description,
            parameters_json_schema=schema,
        )
    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters=spec.get("parameters") or {"type": "object", "properties": {}},
    )


def append_model_turn(contents: list[Any], model_content: Any, results: list[dict[str, Any]], types: Any) -> None:
    """Append Gemini's own message, then the tool outputs, to the same conversation."""
    if model_content is not None:
        contents.append(model_content)
    response_parts = []
    for item in results:
        name = str(item.get("name") or "")
        if not name:
            continue
        payload = item.get("result") if isinstance(item.get("result"), dict) else {"result": item.get("result")}
        response_parts.append(types.Part.from_function_response(name=name, response=payload))
    if response_parts:
        contents.append(types.Content(role="tool", parts=response_parts))


class ToolConversation:
    """One Gemini conversation. The harness appends tool outputs; it does not rebuild the request."""

    def __init__(
        self,
        *,
        system: str,
        user_content: str,
        tool_declarations: list[dict[str, Any]],
        history: list[dict[str, Any]] | None = None,
        temperature: float,
    ) -> None:
        from google.genai import types

        self._types = types
        self._client = get_vertex_client()
        self._model = _model()
        # Gemini 3+ (global): function tools + Google Search grounding on one turn.
        # Gemini 2.5 rejects that mix — keep VERTEX_GEMINI_MODEL on 3.x for search.
        # Do NOT set response_mime_type with tools — Gemini rejects / hangs on that combo.
        self._config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            tools=[
                types.Tool(
                    function_declarations=[_function_declaration(spec, types) for spec in tool_declarations]
                ),
                types.Tool(google_search=types.GoogleSearch()),
            ],
        )
        self.contents: list[Any] = []
        for turn in history or []:
            role = turn.get("role") or "user"
            text = turn.get("text") or ""
            if text:
                self.contents.append(
                    types.Content(
                        role=role if role in ("user", "model") else "user",
                        parts=[types.Part.from_text(text=text)],
                    )
                )
        self.contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_content)]))
        self._last_content: Any = None

    def complete(self) -> dict[str, Any]:
        """
        One model reply on this conversation. Returns:
          {"kind": "tool_calls", "calls": [{"name", "arguments"}, ...], "text": str}
          {"kind": "text", "text": str}
          {"kind": "error", "message": str}
        """
        import phoenix_tracing

        with phoenix_tracing.llm_span(
            "vertex_gemini",
            model=self._model,
            input_value=_last_user_text(self.contents)[:4000],
        ) as span:
            try:
                result = self._client.models.generate_content(
                    model=self._model,
                    contents=self.contents,
                    config=self._config,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("vertex_generate_failed: %s: %s", type(exc).__name__, exc)
                phoenix_tracing.set_output(
                    span,
                    {"kind": "error", "message": "unavailable", "error": f"{type(exc).__name__}: {exc}"[:500]},
                )
                return {"kind": "error", "message": "unavailable"}

            calls, texts, content = _read_candidate(result)
            self._last_content = content
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
                out = {"kind": "text", "text": text}
                phoenix_tracing.set_output(span, out)
                return out
            phoenix_tracing.set_output(span, {"kind": "error", "message": "empty"})
            return {"kind": "error", "message": "empty"}

    def add_tool_results(self, results: list[dict[str, Any]]) -> None:
        append_model_turn(self.contents, self._last_content, results, self._types)
        self._last_content = None

    def add_argument_error(self, message: str) -> None:
        self._last_content = None
        note = f"Argument error to fix: {message}"
        self.contents.append(
            self._types.Content(role="user", parts=[self._types.Part.from_text(text=note)])
        )


def _last_user_text(contents: list[Any]) -> str:
    for content in reversed(contents):
        if getattr(content, "role", None) != "user":
            continue
        for part in list(getattr(content, "parts", None) or []):
            text = getattr(part, "text", None)
            if text:
                return str(text)
    return ""


def _read_candidate(result: Any) -> tuple[list[dict[str, Any]], list[str], Any]:
    calls: list[dict[str, Any]] = []
    texts: list[str] = []
    try:
        candidates = getattr(result, "candidates", None) or []
        if not candidates:
            return calls, texts, None
        content = candidates[0].content
        for part in getattr(content, "parts", None) or []:
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
        return calls, texts, content
    except Exception:  # noqa: BLE001
        return [], [], None


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
