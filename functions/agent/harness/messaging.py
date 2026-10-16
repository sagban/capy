"""User-facing message sanitization — never leak stack, ids, or tool names."""

from __future__ import annotations

import re

GRACEFUL_FAILURE = "couldn’t get that just now — try again, or log it from Food Log"

_TECH_TERMS = re.compile(
    r"\b("
    r"vertex|gemini|firebase|firestore|langgraph|langchain|openai|anthropic|"
    r"usda|fdc|api|http|json|swift|python|gcp|google cloud|secret manager|"
    r"cloud functions?|emulator|harness|traceback|stack trace|model |"
    r"tool_call|function.?call|token|bearer"
    r")\b",
    re.I,
)
_ID_LIKE = re.compile(
    r"\b(usda_|seed_|web_|tpl_|mem_)[a-z0-9_]+\b|"
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)
# HTTP 4xx/5xx only — never strip arbitrary 3-digit amounts (calories/grams).
_STATUS = re.compile(
    r"\b(http\s*)?status\s*[:=]?\s*[45]\d{2}\b|"
    r"\berror\s*\(\s*[45]\d{2}\s*\)|"
    r"\bHTTP/?\d*\s+[45]\d{2}\b|"
    r"\bHTTP\s*[45]\d{2}\b",
    re.I,
)
_URL = re.compile(r"https?://\S+", re.I)


def sanitize_assistant_message(
    text: str | None,
    *,
    fallback: str | None = None,
    allow_empty: bool = False,
) -> str:
    raw = (text or "").strip()
    if not raw:
        if allow_empty:
            return ""
        return fallback or GRACEFUL_FAILURE
    cleaned = _URL.sub("", raw)
    cleaned = _ID_LIKE.sub("", cleaned)
    cleaned = _TECH_TERMS.sub("", cleaned)
    cleaned = _STATUS.sub("", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip(" -—:\n\t")
    if len(cleaned) < 2:
        if allow_empty:
            return ""
        return fallback or GRACEFUL_FAILURE
    return cleaned
