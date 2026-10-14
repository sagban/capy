"""Meal harness: resolve, suggestions, phrase."""

from harness.context import compact_context_pack
from harness.execute import run_calls
from harness.outcomes import normalize_outcome

__all__ = [
    "compact_context_pack",
    "normalize_outcome",
    "run_calls",
]
