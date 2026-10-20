"""Optional Arize Phoenix tracing for the meal harness.

Enabled when CAPY_PHOENIX=1 or PHOENIX_COLLECTOR_ENDPOINT is set.
Fails soft (no-op) if packages/env are missing — never breaks interpret_meal.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator, Optional

logger = logging.getLogger("capy.phoenix")

_ENABLED = False
_TRACER = None
_TRIED = False


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _collector_base() -> str:
    raw = (os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") or "").strip()
    if not raw:
        raw = "http://127.0.0.1:6006"
    return raw.rstrip("/")


def setup() -> bool:
    """Register Phoenix OTEL once. Safe to call repeatedly; never raises."""
    global _ENABLED, _TRACER, _TRIED
    if _ENABLED:
        return True
    if _TRIED:
        return False
    _TRIED = True

    if _truthy("CAPY_MOCK_AGENT"):
        return False
    # Explicit off wins (even if PHOENIX_COLLECTOR_ENDPOINT is still in the env).
    # Needed on macOS: Phoenix/Arrow curl_global_init SIGSEGVs in gunicorn fork children.
    _phoenix = (os.environ.get("CAPY_PHOENIX") or "").strip().lower()
    if _phoenix in ("0", "false", "no", "off"):
        return False
    if not _truthy("CAPY_PHOENIX") and not (os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") or "").strip():
        return False

    base = _collector_base()
    os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", base)
    # Explicit OTLP HTTP path avoids protocol-inference bugs that can wedge the worker.
    traces_endpoint = base if base.endswith("/v1/traces") else f"{base}/v1/traces"

    try:
        from phoenix.otel import register
        from opentelemetry import trace

        project = os.environ.get("PHOENIX_PROJECT_NAME") or "capy-harness"
        # No auto_instrument — LangChain/GenAI instrumentors are heavy and have
        # crashed the Firebase Python worker (socket hang up). Manual spans only.
        provider = register(
            project_name=project,
            endpoint=traces_endpoint,
            protocol="http/protobuf",
            batch=False,
            auto_instrument=False,
            set_global_tracer_provider=True,
            verbose=False,
        )
        _TRACER = trace.get_tracer("capy.harness", "1.0.0")
        _ENABLED = True
        setup._provider = provider  # type: ignore[attr-defined]
        logger.info("Phoenix tracing on → %s project=%s", traces_endpoint, project)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phoenix tracing disabled: %s", exc)
        _ENABLED = False
        _TRACER = None
        return False


def enabled() -> bool:
    return _ENABLED


def _set_kind(span: Any, kind: str) -> None:
    span.set_attribute("openinference.span.kind", kind)


def _set_io(
    span: Any,
    *,
    input_value: Optional[str] = None,
    output_value: Optional[str] = None,
) -> None:
    if input_value is not None:
        span.set_attribute("input.value", input_value[:12000])
        span.set_attribute(
            "input.mime_type",
            "application/json" if input_value[:1] in "{[" else "text/plain",
        )
    if output_value is not None:
        span.set_attribute("output.value", output_value[:12000])
        span.set_attribute(
            "output.mime_type",
            "application/json" if output_value[:1] in "{[" else "text/plain",
        )


def _dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return str(value)


@contextmanager
def chain_span(name: str, *, input_value: str = "") -> Iterator[Any]:
    setup()
    if not _ENABLED or _TRACER is None:
        yield None
        return
    with _TRACER.start_as_current_span(name) as span:
        _set_kind(span, "CHAIN")
        _set_io(span, input_value=input_value)
        try:
            yield span
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            raise


@contextmanager
def llm_span(name: str = "vertex_gemini", *, model: str = "", input_value: str = "") -> Iterator[Any]:
    setup()
    if not _ENABLED or _TRACER is None:
        yield None
        return
    with _TRACER.start_as_current_span(name) as span:
        _set_kind(span, "LLM")
        if model:
            span.set_attribute("llm.model_name", model)
        span.set_attribute("llm.provider", "google")
        span.set_attribute("llm.system", "vertex_ai")
        _set_io(span, input_value=input_value)
        try:
            yield span
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            raise


@contextmanager
def tool_span(name: str, *, arguments: Any = None) -> Iterator[Any]:
    setup()
    if not _ENABLED or _TRACER is None:
        yield None
        return
    with _TRACER.start_as_current_span(name or "tool") as span:
        _set_kind(span, "TOOL")
        span.set_attribute("tool.name", name or "")
        _set_io(span, input_value=_dumps(arguments or {}))
        try:
            yield span
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            raise


def set_output(span: Any, value: Any) -> None:
    if span is None:
        return
    text = value if isinstance(value, str) else _dumps(value)
    _set_io(span, output_value=text)


def set_attrs(span: Any, attrs: dict[str, Any]) -> None:
    if span is None:
        return
    for key, value in (attrs or {}).items():
        if value is None:
            continue
        try:
            if isinstance(value, (str, bool, int, float)):
                span.set_attribute(key, value)
            else:
                span.set_attribute(key, _dumps(value)[:2000])
        except Exception:  # noqa: BLE001
            continue


def tool_result_summary(name: str, result: Any) -> dict[str, Any]:
    """Compact Phoenix output for harness tool spans."""
    if not isinstance(result, dict):
        return {"ok": True, "tool": name}
    out: dict[str, Any] = {
        "tool": name,
        "intent": result.get("intent"),
        "error": result.get("error"),
        "warnings": result.get("warnings") or [],
    }
    facts = result.get("phraseFacts") or {}
    if facts.get("reason"):
        out["reason"] = facts.get("reason")
    if facts.get("dropped"):
        out["dropped"] = facts.get("dropped")
    options = result.get("suggestionOptions") or []
    if options:
        out["optionCount"] = len(options)
        sources: list[str] = []
        for opt in options:
            for item in opt.get("items") or []:
                src = item.get("source")
                if src and src not in sources:
                    sources.append(str(src))
        out["optionSources"] = sources
    pending = result.get("pendingAction")
    if isinstance(pending, dict):
        out["pending"] = pending.get("type")
        payload = pending.get("payload") or {}
        resolved = payload.get("resolvedItems") or []
        if resolved:
            out["resolvedSources"] = [str(i.get("source") or "") for i in resolved]
            out["resolvedNames"] = [str(i.get("displayName") or "") for i in resolved][:6]
        if payload.get("reason"):
            out["pendingReason"] = payload.get("reason")
    return out
