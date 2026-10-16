"""User-visible assistant message normalization.

Model prose is not rewritten with keyword or infra filters. Structured outcomes
are validated in ``normalize_outcome`` / ``InterpretMealResponse``; harness
templates in ``format_message`` are authored code, not scraped model text.
"""

from __future__ import annotations

import re

GRACEFUL_FAILURE = "couldn’t get that just now — try again, or log it from Food Log"

_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def _normalize_whitespace(text: str) -> str:
    """Cosmetic whitespace only — does not alter words or remove content."""
    collapsed = _MULTI_NEWLINE.sub("\n\n", text)
    lines = [_MULTI_SPACE.sub(" ", line).strip() for line in collapsed.split("\n")]
    return "\n".join(lines).strip()


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
    return _normalize_whitespace(raw)
