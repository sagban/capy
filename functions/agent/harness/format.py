"""User-visible text: model draft, then a factual line if the model wrote nothing."""

from __future__ import annotations

from typing import Any

from agent.harness.messaging import looks_like_structured_dump, sanitize_assistant_message


def _join_names(names: list[str], *, limit: int = 4) -> str:
    clean = [n for n in names if n]
    if not clean:
        return ""
    shown = clean[:limit]
    extra = len(clean) - len(shown)
    if len(shown) == 1:
        text = shown[0]
    elif len(shown) == 2:
        text = f"{shown[0]} and {shown[1]}"
    else:
        text = ", ".join(shown[:-1]) + f", and {shown[-1]}"
    if extra > 0:
        text += f" (+{extra} more)"
    return text


def _remaining_bits(budget: dict[str, Any] | None) -> str:
    if not isinstance(budget, dict):
        return ""
    parts: list[str] = []
    if budget.get("calories") is not None:
        parts.append(f"{int(round(float(budget['calories'])))} cal")
    if budget.get("proteinG") is not None:
        parts.append(f"~{int(round(float(budget['proteinG'])))} g protein")
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} and {parts[1]}"


def summary_from_options(outcome: dict[str, Any]) -> str:
    """1–2 short paragraphs: day context + a few picks that keep them on track."""
    options = [option for option in (outcome.get("options") or []) if isinstance(option, dict)]
    if not options:
        return ""

    day = outcome.get("day") if isinstance(outcome.get("day"), dict) else {}
    eaten = [str(n).strip() for n in (day.get("eaten") or []) if str(n).strip()]
    # Prefer slot budget for the pick; fall back to day remaining.
    budget = outcome.get("budget") if isinstance(outcome.get("budget"), dict) else {}
    day_remaining = day.get("remaining") if isinstance(day.get("remaining"), dict) else {}
    left = _remaining_bits(budget) or _remaining_bits(day_remaining)

    eaten_bit = _join_names(eaten)
    if eaten_bit and left:
        para1 = (
            f"So far today you've logged {eaten_bit}. "
            f"With about {left} left for this meal, these keep you on track:"
        )
    elif eaten_bit:
        para1 = f"So far today you've logged {eaten_bit}. Here are a few picks that fit what's left:"
    elif left:
        para1 = f"Clean slate so far — you've got about {left} to work with. A few solid options:"
    else:
        para1 = "A few picks that fit what's left:"

    bits: list[str] = []
    for option in options[:3]:
        title = str(option.get("title") or "Option").strip() or "Option"
        totals = option.get("totals") or {}
        cal = totals.get("calories")
        pro = totals.get("proteinG")
        if cal is None:
            bits.append(title)
            continue
        protein_bit = f", {int(round(float(pro)))} g protein" if pro is not None else ""
        if option.get("fit") == "over":
            bits.append(
                f"{title} ({int(round(float(cal)))} cal{protein_bit} — a bit over)"
            )
        else:
            bits.append(f"{title} ({int(round(float(cal)))} cal{protein_bit})")
    if len(bits) == 1:
        para2 = f"{bits[0]}. Want that, or something else?"
    elif len(bits) == 2:
        para2 = f"{bits[0]}, or {bits[1]}. Want one of these, or something else?"
    else:
        para2 = f"{', '.join(bits[:-1])}, or {bits[-1]}. Want one of these, or something else?"

    return f"{para1}\n\n{para2}"


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
    if food and reason in {"not_found", "deadline", "venue_needs_citation"}:
        if reason == "venue_needs_citation":
            return (
                f"I need menu nutrition for {food}. Ask again and I'll look it up, "
                "or log it from Food Log."
            )
        return f"I couldn't find {food}. A brand or a plainer name helps, or log it from Food Log."
    return ""


def no_suggestion_line(outcome: dict[str, Any]) -> str:
    if outcome.get("reason") != "no suggestion survived":
        return ""
    dropped = [str(row) for row in (outcome.get("dropped") or [])]
    day = outcome.get("day") if isinstance(outcome.get("day"), dict) else {}
    eaten = [str(n).strip() for n in (day.get("eaten") or []) if str(n).strip()]
    eaten_bit = _join_names(eaten)
    prefix = f"Looking at {eaten_bit} already logged — " if eaten_bit else ""
    if any("venue_needs_citation" in row for row in dropped):
        return (
            f"{prefix}I need that place's menu nutrition to size a pick. "
            "Ask again and I'll look it up, or log it from Food Log."
        )
    return (
        f"{prefix}I couldn't land a solid pick from those drafts. "
        "Name a food you have on hand, or log it from Food Log."
    )


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


def confirm_log_line(outcome: dict[str, Any]) -> str:
    items = outcome.get("items") or []
    names: list[str] = []
    for raw in items:
        if isinstance(raw, dict):
            name = str(raw.get("displayName") or raw.get("name") or "").strip()
            if name:
                names.append(name)
    if not names:
        return ""
    if len(names) == 1:
        return f"Ready to log {names[0]}."
    if len(names) == 2:
        return f"Ready to log {names[0]} and {names[1]}."
    return f"Ready to log {', '.join(names[:-1])}, and {names[-1]}."


def _factual_supplement(outcome: dict[str, Any]) -> str:
    return (
        summary_from_options(outcome)
        or clarify_question(outcome)
        or confirm_log_line(outcome)
        or no_suggestion_line(outcome)
        or memory_line(outcome)
        or menu_line(outcome)
    )


def format_message(*, draft: str, outcome: dict[str, Any]) -> str:
    # Prefer the model's human prose. Never show tool/ResolvedItem dumps.
    # Harness lines are fallback only when the draft is empty or was scrubbed.
    text = "" if looks_like_structured_dump(draft) else sanitize_assistant_message(draft, allow_empty=True)
    if text:
        return text
    return _factual_supplement(outcome)
