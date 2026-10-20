"""Map user-facing response style dial to Gemini sampling and system instructions."""

from __future__ import annotations

from typing import Final

# Stored on profile / interpret `context` — not shown as "temperature" in UI.
DEFAULT_RESPONSE_STYLE: Final[str] = "balanced"

# balanced = default (0.5); precise is tighter (0.2); creative adds flexibility (0.8).
_STYLE_TO_TEMPERATURE: Final[dict[str, float]] = {
    "precise": 0.2,
    "balanced": 0.5,
    "creative": 0.8,
}

# One block per style — only the active style is injected into the system prompt per turn.
_STYLE_INSTRUCTIONS: Final[dict[str, str]] = {
    "precise": (
        "Be literal and clear. State facts from the pack and tools; skip fluff, but still "
        "use full sentences a person can follow. Never dump tool or system output into chat."
    ),
    "balanced": (
        "Stay grounded in the pack and tools. Prefer a warm, complete reply: what you did, "
        "how it fits what's left, and what's next. Never dump tool or system output into chat."
    ),
    "creative": (
        "Stay accurate, with warmer varied phrasing and light personality. Be communicative "
        "without padding or inventing nutrition facts. Never dump tool or system output into chat."
    ),
}


def normalize_response_style(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    if key in _STYLE_TO_TEMPERATURE:
        return key
    return DEFAULT_RESPONSE_STYLE


def temperature_for_response_style(raw: str | None) -> float:
    return _STYLE_TO_TEMPERATURE[normalize_response_style(raw)]


def instruction_block_for_response_style(raw: str | None) -> str:
    """LLM-facing reply-style rules for this turn only (not all dial options)."""
    style = normalize_response_style(raw)
    body = _STYLE_INSTRUCTIONS[style]
    return f"Reply style (semantic.responseStyle — obey)\n{body}"
