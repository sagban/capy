"""One model turn: all tools, all function calls. No skill router and no stock replies."""

from __future__ import annotations

import os
from typing import Any

from harness.declarations import TOOL_DECLARATIONS
from harness.execute import lookup_menu
from harness.mock_turn import pop_mock_turn
from schemas import InterpretMealRequest, ItemDraft

SYSTEM_PROMPT = """You are Capy, a food log assistant. You never invent calories, protein, carbs, or fat.
The app computes macros from per-100g values and grams.

Call a tool when the user wants to log, change an open log, suggest a meal, repeat a logged meal,
correct a diary entry, or save/remove a memory note. "What should I eat" is compose_suggestions,
not a text reply. You may call more than one tool in the same turn. You may call lookup_menu once
before compose_suggestions when a restaurant is named. save_memory can accompany any other tool.

If workingMemory has an open chip and the user is accepting that portion or food, call accept_option
with that option id. Do not call resolve_meal again with a different gram amount.

Answer from the context pack with text only when the user is asking what they already ate or what
is left. Do not claim that nothing was logged when the diary has entries.

Tool arguments:
- resolve_meal items: foodQuery, optional brandOrVenue, quantity, unit, aliases, rawText.
  aliases are other names to search. Do not invent grams. Omit quantity when the user did not say how much.
- compose_suggestions: 2 or 3 different meals for the slot they asked for. Every item needs
  foodQuery, quantity, and unit (grams are fine). Size the meal to that slot's budget in the
  context. Respect diets. Do not write calorie or macro totals; the app computes those.
- repeat_prior_meal: entryIds from the diary context.
- correct_entry: entryId, itemIndex, op set_amount|replace|remove.
- edit_draft / log_from_suggestion ops: set_amount, remove, add, replace. Use the open draftLog
  or lastSuggestionOptions in the context.
- lookup_menu returns names only. Ignore any numbers.

Write the reply in this same turn, including when you call a tool. The app shows your sentence next to any cards.
"""


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    items = getattr(value, "items", None)
    if callable(items):
        try:
            return {str(k): _plain(v) for k, v in items()}
        except Exception:  # noqa: BLE001
            return value
    return value


def _validate_calls(calls: list[dict[str, Any]]) -> str | None:
    if not calls:
        return None
    for call in calls:
        name = call.get("name")
        args = call.get("arguments") or {}
        try:
            if name == "resolve_meal":
                items = args.get("items") or []
                if not items:
                    return "resolve_meal needs items"
                for raw in items:
                    ItemDraft.model_validate(raw)
            elif name == "edit_draft":
                if not isinstance(args.get("ops"), list) or not args.get("ops"):
                    return "edit_draft needs ops"
            elif name == "log_from_suggestion":
                if not args.get("optionId"):
                    return "log_from_suggestion needs optionId"
            elif name == "compose_suggestions":
                drafts = args.get("drafts") or []
                if not drafts:
                    return "compose_suggestions needs drafts"
            elif name == "repeat_prior_meal":
                if not args.get("entryIds"):
                    return "repeat_prior_meal needs entryIds"
            elif name == "correct_entry":
                if args.get("entryId") is None or args.get("itemIndex") is None or not args.get("op"):
                    return "correct_entry needs entryId, itemIndex, op"
                if args.get("op") not in {"set_amount", "replace", "remove"}:
                    return "correct_entry op"
            elif name == "accept_option":
                if not args.get("optionId"):
                    return "accept_option needs optionId"
            elif name == "lookup_menu":
                if not str(args.get("venue") or "").strip():
                    return "lookup_menu needs venue"
            elif name == "save_memory":
                op = args.get("op")
                if op == "add" and not args.get("text"):
                    return "save_memory add needs text"
                if op == "remove" and not args.get("noteId"):
                    return "save_memory remove needs noteId"
                if op not in {"add", "remove"}:
                    return "save_memory op"
            else:
                return f"unknown tool {name}"
        except Exception as exc:  # noqa: BLE001
            return str(exc)
    return None


def _generate(system: str, user: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    if os.environ.get("CAPY_MOCK_AGENT") == "1":
        scripted = pop_mock_turn()
        if scripted:
            return scripted
        return {"kind": "text", "text": ""}
    from vertex_gemini import generate_with_tools

    return generate_with_tools(
        system=system,
        user_content=user,
        tool_declarations=TOOL_DECLARATIONS,
        history=history,
    )


def _normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    kind = result.get("kind")
    if kind == "tool_call" and result.get("name"):
        return {
            "kind": "tool_calls",
            "calls": [{"name": result["name"], "arguments": _plain(result.get("arguments") or {})}],
            "text": "",
        }
    if kind == "tool_calls":
        calls = []
        for call in result.get("calls") or []:
            calls.append(
                {
                    "name": call.get("name"),
                    "arguments": _plain(call.get("arguments") or {}),
                }
            )
        return {"kind": "tool_calls", "calls": calls, "text": result.get("text") or ""}
    if kind == "text":
        return {"kind": "text", "text": result.get("text") or ""}
    if kind == "json":
        data = result.get("data") or {}
        text = data.get("assistantMessage") or data.get("text") or ""
        return {"kind": "text", "text": str(text)}
    if kind == "error":
        return {"kind": "error", "message": result.get("message") or "unavailable"}
    return {"kind": "error", "message": "unavailable"}


def model_turn(
    req: InterpretMealRequest,
    context_pack: str,
    *,
    validation_error: str = "",
    prior_text: str = "",
) -> dict[str, Any]:
    """Return tool_calls, text, bad_args, or error."""
    history = [
        {"role": turn.role if turn.role in {"user", "model"} else "user", "text": turn.text}
        for turn in (req.conversation.recentTurns or [])[-8:]
    ]
    note = f"\nArgument error to fix: {validation_error}" if validation_error else ""
    prior = f"\nYour previous answer:\n{prior_text}" if prior_text else ""
    user = f"{context_pack}{note}{prior}\n\nUser message:\n{req.utterance}"
    first = _normalize_result(_generate(SYSTEM_PROMPT, user, history))
    if first["kind"] == "error":
        return first
    if first["kind"] == "text":
        return first

    calls = first["calls"]
    names = [c["name"] for c in calls]
    if names and set(names) == {"lookup_menu"}:
        menu = lookup_menu(str(calls[0]["arguments"].get("venue") or ""))
        follow = (
            f"{user}\n\nMenu names for {menu.get('venue')}: {menu.get('items')}\n"
            "Now call compose_suggestions or answer. Do not call lookup_menu again."
        )
        second = _normalize_result(_generate(SYSTEM_PROMPT, follow, history))
        if second["kind"] == "error":
            return second
        if second["kind"] == "text":
            return second
        calls = [c for c in second["calls"] if c["name"] != "lookup_menu"]
        if not calls:
            return {"kind": "text", "text": second.get("text") or ""}

    error = _validate_calls(calls)
    if error:
        return {"kind": "bad_args", "message": error, "calls": calls, "text": first.get("text") or ""}
    return {"kind": "tool_calls", "calls": calls, "text": first.get("text") or ""}
