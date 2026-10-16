"""User-visible text: model draft, then a factual line if the model wrote nothing."""

from __future__ import annotations

from typing import Any

from agent.harness.messaging import sanitize_assistant_message


def summary_from_options(outcome: dict[str, Any]) -> str:
    options = [option for option in (outcome.get("options") or []) if isinstance(option, dict)]
    if not options:
        return ""
    budget = outcome.get("budget") or {}
    parts: list[str] = []
    calories = budget.get("calories")
    protein = budget.get("proteinG")
    if calories is not None:
        line = f"Up to {int(round(float(calories)))} cal"
        if protein is not None:
            line += f", about {int(round(float(protein)))} g protein left"
        parts.append(line + ".")
    for option in options:
        title = option.get("title") or "Option"
        totals = option.get("totals") or {}
        cal = totals.get("calories")
        pro = totals.get("proteinG")
        if cal is None:
            continue
        fit = "over" if option.get("fit") == "over" else "fits"
        protein_bit = f", {int(round(float(pro)))} g protein" if pro is not None else ""
        parts.append(f"{title}: {int(round(float(cal)))} cal{protein_bit}, {fit}.")
    return "\n".join(parts)


def clarify_question(outcome: dict[str, Any]) -> str:
    labels = [option for option in (outcome.get("options") or []) if isinstance(option, str) and option.strip()]
    food = str(outcome.get("food") or "").strip()
    kind = str(outcome.get("kind") or "")
    reason = str(outcome.get("reason") or "")
    quantity = outcome.get("quantity")
    unit = str(outcome.get("unit") or "").strip()
    if kind == "clarify_portion" or reason == "need_amount":
        if quantity and unit and food:
            return f"I don't have a weight for {quantity:g} {unit} of {food}. How many grams?"
        if quantity and food:
            return f"How many grams for {quantity:g} {food}?"
        return f"How much {food}?" if food else "How much?"
    if len(labels) >= 2:
        shown = ", ".join(labels[:3])
        return f"Which one for {food}? {shown}" if food else shown
    if food and reason in {"not_found", "deadline"}:
        return f"I couldn't find {food}. A brand or a plainer name helps, or log it from Food Log."
    return ""


def no_suggestion_line(outcome: dict[str, Any]) -> str:
    if outcome.get("reason") != "no suggestion survived":
        return ""
    return "I couldn't source a meal from those drafts. Name a food you have, or log it from Food Log."


def memory_line(outcome: dict[str, Any]) -> str:
    notes = [note for note in (outcome.get("memory") or []) if isinstance(note, dict)]
    if not notes:
        return ""
    added = [str(note.get("text") or "").strip() for note in notes if note.get("action") != "delete"]
    added = [text for text in added if text]
    if added:
        return "Noted: " + "; ".join(added[:3]) + "."
    if any(note.get("action") == "delete" for note in notes):
        return "Removed."
    return "Noted."


def menu_line(outcome: dict[str, Any]) -> str:
    venue = str(outcome.get("venue") or "").strip()
    items = [str(item).strip() for item in (outcome.get("items") or []) if str(item).strip()]
    if not venue and not items:
        return ""
    names = ", ".join(items[:8])
    if venue and names:
        return f"{venue}: {names}."
    if names:
        return names + "."
    return f"No menu names for {venue}."


def _factual_supplement(outcome: dict[str, Any]) -> str:
    return (
        summary_from_options(outcome)
        or clarify_question(outcome)
        or no_suggestion_line(outcome)
        or memory_line(outcome)
        or menu_line(outcome)
    )


def format_message(*, draft: str, outcome: dict[str, Any]) -> str:
    text = sanitize_assistant_message(draft, allow_empty=True)
    supplement = _factual_supplement(outcome)
    if text and supplement:
        if supplement.strip() in text or text in supplement:
            return text
        return f"{text.rstrip()}\n\n{supplement}"
    if text:
        return text
    return supplement
