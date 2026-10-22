"""Map user-facing assistance dial to per-turn system instructions."""

from __future__ import annotations

from typing import Final

DEFAULT_ASSISTANCE_LEVEL: Final[str] = "fullAssist"

_LEVEL_INSTRUCTIONS: Final[dict[str, str]] = {
    "fullAssist": (
        "After a log you may offer the next meal or what fits their remaining macros."
    ),
    "guided": (
        "Suggest only when they asked or context clearly invites it (e.g. what should I eat)."
    ),
    "quiet": (
        "Log when they say what they ate; do not suggest unless they asked."
    ),
}


def normalize_assistance_level(raw: str | None) -> str:
    key = (raw or "").strip()
    if key in _LEVEL_INSTRUCTIONS:
        return key
    return DEFAULT_ASSISTANCE_LEVEL


def instruction_block_for_assistance_level(raw: str | None) -> str:
    """LLM-facing assistance rules for this turn only (not all dial options)."""
    level = normalize_assistance_level(raw)
    body = _LEVEL_INSTRUCTIONS[level]
    return (
        f"Assistance (semantic.assistanceLevel — obey)\n{body}\n"
        "Never change the assistance level yourself."
    )
