"""Model writes the chat sentence. A validator drops anything the outcome does not support."""

from __future__ import annotations

import re
from typing import Any

from messaging import sanitize_assistant_message

# Ordinary words, not foods. A leftover noun has to appear in the outcome or context.
_FUNCTION = {
    "a", "an", "the", "of", "and", "or", "with", "for", "to", "your", "you", "i",
    "it", "this", "that", "is", "are", "was", "were", "be", "been", "have", "had",
    "has", "some", "also", "about", "from", "left", "fits", "over", "within",
    "confirm", "which", "one", "these", "those", "on", "at", "in", "my", "me",
    "we", "try", "log", "logged", "logging", "option", "options", "meal", "meals",
    "lunch", "breakfast", "dinner", "snack", "snacks", "grams", "gram", "cal",
    "calories", "protein", "carbs", "fat", "what", "should", "eat", "ate", "how",
    "much", "would", "could", "can", "will", "just", "not", "no", "yes", "ok",
    "okay", "here", "there", "them", "they", "their", "than", "then", "so", "if",
    "but", "ready", "portion", "portions", "update", "updated", "saved", "remember",
    "usual", "today", "yesterday", "under", "more", "less", "half", "both", "all",
    "any", "each", "per", "estimate", "estimated", "web", "found", "please", "want",
    "wants", "like", "likes", "something", "else", "instead", "again", "sounds",
    "good", "great", "sure", "right", "next", "still", "already", "same",
    "different", "small", "large", "little", "big", "new", "old", "first",
    "second", "third", "choice", "choices", "name", "names", "brand", "plain",
    "hot", "cold", "piece", "pieces", "slice", "slices", "bowl", "plate", "side",
    "extra", "without", "rather", "prefer", "wanted", "looking", "think", "maybe",
    "perhaps", "around", "exactly", "roughly", "close", "near", "full", "empty",
    "used", "using", "based", "typically", "often", "never", "always", "before",
    "after", "during", "while", "because", "since", "until", "into", "onto",
    "another", "other", "others", "anything", "everything", "nothing", "thanks",
    "thank", "help", "check", "confirmed", "confirmation", "suggested",
    "suggestion", "suggestions", "fit", "budget", "remaining", "day", "food",
    "foods", "item", "items", "open", "sheet", "card", "cards", "chip", "chips",
    "tap", "type", "amount", "many", "few", "enough", "too", "very", "really",
    "now", "work", "works", "working", "got", "get", "getting", "let", "lets",
    "make", "made", "making", "need", "needs", "needed", "know", "known", "see",
    "look", "looks", "come", "comes", "going", "went", "well", "fine", "done",
    "keep", "kept", "add", "added", "change", "changed", "remove", "removed",
    "correct", "corrected", "correction", "repeat", "repeated", "tomorrow",
    "morning", "evening", "night", "later", "earlier", "time", "times",
    "normally", "total", "totals", "missing", "ask", "asked", "question",
    "answer", "say", "said", "tell", "show", "pick", "picked", "choose", "chose",
    "when", "where", "who", "why", "did", "does", "don", "doesn", "isn", "aren",
    "couldn", "didn", "wasn", "won", "cant", "cannot",
}

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def _numbers_in(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text or "")


def collect_allowed_numbers(*blobs: Any) -> set[str]:
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            number = float(value)
            found.add(str(int(round(number))))
            if abs(number - round(number)) > 1e-6:
                found.add(f"{number:.1f}".rstrip("0").rstrip("."))
                found.add(str(number))
            return
        if isinstance(value, str):
            found.update(_numbers_in(value))
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    for blob in blobs:
        walk(blob)
    return found


def _number_allowed(token: str, allowed: set[str]) -> bool:
    if token in allowed:
        return True
    try:
        value = float(token)
    except ValueError:
        return False
    for raw in allowed:
        try:
            if abs(float(raw) - value) <= 0.51:
                return True
        except ValueError:
            continue
    return False


def _allowed_tokens(*blobs: Any) -> set[str]:
    parts: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    for blob in blobs:
        walk(blob)
    return set(re.findall(r"[a-z0-9]+", " ".join(parts).lower()))


def _content_tokens(sentence: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", sentence.lower())
    return [token for token in tokens if token not in _FUNCTION and len(token) > 2]


def _token_known(token: str, allowed: set[str]) -> bool:
    if token in allowed:
        return True
    if len(token) > 3 and token.endswith("s") and token[:-1] in allowed:
        return True
    return False


def _has_options(blobs: tuple[Any, ...]) -> bool:
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        options = blob.get("options") or []
        if any(isinstance(option, dict) for option in options):
            return True
    return False


def validate_message(text: str, *blobs: Any) -> str:
    """Drop ungrounded numbers. On a log, also drop foods that are not in the outcome.

    A suggestion reply may use normal words ("light", "short on protein"). Those are not foods.
    """
    allowed_numbers = collect_allowed_numbers(*blobs)
    allowed_tokens = _allowed_tokens(*blobs)
    check_foods = not _has_options(blobs)
    kept: list[str] = []
    for match in _SENTENCE.finditer(text or ""):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        content = _content_tokens(sentence)
        if not content:
            continue
        if any(not _number_allowed(token, allowed_numbers) for token in _numbers_in(sentence)):
            continue
        if check_foods and any(not _token_known(token, allowed_tokens) for token in content):
            continue
        kept.append(sentence)
    cleaned = " ".join(kept).strip()
    return sanitize_assistant_message(cleaned, allow_empty=True)


def summary_from_options(outcome: dict[str, Any]) -> str:
    """Factual reply from the suggestion outcome, used when the model sentence is empty."""
    options = [option for option in (outcome.get("options") or []) if isinstance(option, dict)]
    if not options:
        return ""
    budget = outcome.get("budget") or {}
    parts: list[str] = []
    calories = budget.get("calories")
    protein = budget.get("proteinG")
    if calories is not None:
        line = f"This meal can be up to {int(round(float(calories)))} cal"
        if protein is not None:
            line += f" with about {int(round(float(protein)))} g protein still left"
        parts.append(line + ".")
    for option in options:
        title = option.get("title") or "Option"
        totals = option.get("totals") or {}
        cal = totals.get("calories")
        pro = totals.get("proteinG")
        foods = [name for name in (option.get("items") or []) if name]
        if cal is None:
            continue
        fit = "over that" if option.get("fit") == "over" else "within that"
        food_bit = f" ({', '.join(foods)})" if foods else ""
        protein_bit = f", {int(round(float(pro)))} g protein" if pro is not None else ""
        parts.append(f"{title}{food_bit} is {int(round(float(cal)))} cal{protein_bit}, {fit}.")
    return " ".join(parts)


def clarify_question(outcome: dict[str, Any]) -> str:
    """Ask in text when a food or amount is still open. No chips."""
    labels = [option for option in (outcome.get("options") or []) if isinstance(option, str) and option.strip()]
    food = str(outcome.get("food") or "").strip()
    if labels:
        shown = ", ".join(labels[:3])
        return f"Which one for {food}? {shown}" if food else shown
    if food and outcome.get("reason") in {"need_amount", "not_found", "deadline"}:
        if outcome.get("reason") == "need_amount":
            return f"How much {food}?"
        return f"I couldn't find {food}. A brand or a plainer name helps, or log it from Food Log."
    return ""


def phrase_message(
    *,
    draft: str,
    outcome: dict[str, Any],
    context_pack: str,
    user_text: str,
    generate,
) -> str:
    """Show the model's sentence. No second model call. Cards still get a factual line if it wrote nothing."""
    del context_pack, user_text, generate
    text = sanitize_assistant_message(draft, allow_empty=True)
    if text:
        return text
    return summary_from_options(outcome) or clarify_question(outcome)
