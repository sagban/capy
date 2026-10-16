"""LangChain @tool functions and their argument models."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from agent.harness.meal_budget import AppetiteLevel

from langchain_core.tools import BaseTool, InjectedToolArg, tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field, ValidationError, model_validator

from schemas import ItemDraft
from agent.harness.tools.common import memory_proposal
from agent.harness.tools import jobs

Kind = Literal["primary", "suggestions", "memory"]
Ctx = Annotated[dict[str, Any], InjectedToolArg]


class DraftFood(BaseModel):
    foodQuery: str
    quantity: float
    unit: str
    brandOrVenue: Optional[str] = None
    aliases: list[str] = Field(default_factory=list, description="Other names to search.")


class DraftMeal(BaseModel):
    title: str
    items: list[DraftFood]


class StatedBudget(BaseModel):
    calories: Optional[float] = None
    proteinG: Optional[float] = None
    carbsG: Optional[float] = None
    fatG: Optional[float] = None


class DraftOp(BaseModel):
    op: Literal["set_amount", "remove", "add", "replace"]
    index: Optional[int] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    item: Optional[ItemDraft] = None


class NewEntryArgs(BaseModel):
    items: Optional[list[ItemDraft]] = Field(
        default=None,
        description="Foods to resolve into a new meal entry for the user to confirm.",
    )
    ops: Optional[list[DraftOp]] = Field(
        default=None,
        description="Edits on the staged entry before confirm (set_amount, remove, add, replace).",
    )
    optionId: Optional[str] = Field(
        default=None,
        description="Start from a stored suggestion (lastSuggestionOptions id) before ops/items.",
    )

    @model_validator(mode="after")
    def _needs_payload(self) -> NewEntryArgs:
        if not self.items and not self.ops and not self.optionId:
            raise ValueError("new_entry needs items, ops, or optionId")
        return self


class ComposeSuggestionsArgs(BaseModel):
    drafts: list[DraftMeal] = Field(min_length=1)
    mealSlot: Optional[str] = None
    venue: Optional[str] = None
    budget: Optional[StatedBudget] = None
    appetite: Optional[AppetiteLevel] = Field(
        default=None,
        description="light | normal | hearty — scales the harness guide from user intent. Ignored when budget is set.",
    )


class RepeatPriorMealArgs(BaseModel):
    entryIds: list[str] = Field(min_length=1)


class EditEntryArgs(BaseModel):
    entryId: str
    itemIndex: int
    op: Literal["set_amount", "replace", "remove"]
    quantity: Optional[float] = None
    unit: Optional[str] = None
    item: Optional[ItemDraft] = None


class DeleteEntryArgs(BaseModel):
    entryId: str
    dayKey: Optional[str] = Field(
        default=None,
        description="Calendar day key (YYYY-MM-DD). Omit when the entry is on today in the pack.",
    )


class SaveMemoryArgs(BaseModel):
    op: Literal["add", "remove"]
    text: Optional[str] = None
    noteId: Optional[str] = None

    @model_validator(mode="after")
    def _complete(self) -> SaveMemoryArgs:
        if self.op == "add" and not (self.text or "").strip():
            raise ValueError("save_memory add needs text")
        if self.op == "remove" and not (self.noteId or "").strip():
            raise ValueError("save_memory remove needs noteId")
        return self


def _is_schema_title(key: str, value: Any) -> bool:
    """JSON Schema `title` is a string. A property named title is an object schema."""
    return key == "title" and isinstance(value, str)


def _gemini_schema(node: Any) -> Any:
    """Gemini function parameters: drop JSON Schema title/default, keep a property named title."""
    if isinstance(node, list):
        return [_gemini_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    if "anyOf" in node:
        variants = [item for item in node["anyOf"] if item != {"type": "null"}]
        if len(variants) == 1:
            merged = {
                k: v
                for k, v in node.items()
                if k not in {"anyOf", "default"} and not _is_schema_title(k, v)
            }
            merged.update(variants[0])
            return _gemini_schema(merged)
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "default" or _is_schema_title(key, value):
            continue
        out[key] = _gemini_schema(value)
    return out


def _declaration(lc: BaseTool) -> dict[str, Any]:
    payload = convert_to_openai_tool(lc)["function"]
    return {
        "name": payload["name"],
        "description": payload.get("description") or "",
        "parameters": _gemini_schema(payload.get("parameters") or {"type": "object", "properties": {}}),
    }


@tool(args_schema=NewEntryArgs)
def new_entry(
    items: list[ItemDraft] | None = None,
    ops: list[DraftOp] | None = None,
    optionId: Optional[str] = None,
    ctx: Ctx = None,
) -> dict[str, Any]:
    """Stage a new meal for human-in-the-loop confirm (confirm_log) before anything is written to the diary.

    When to use: The user is logging or correcting a staged meal — they named foods, want to log a
    prior suggestion, or are tweaking the open draft (ops). Safe to combine with compose_suggestions
    or save_memory in the same turn.

    When not to use: If they only ask what they ate or what's left, answer from the context pack
    in text without calling a tool.

    Args:
        items: One row per food (foodQuery, quantity, unit). Omit quantity/unit only if they did not
            say how much. Example: foodQuery rice, quantity 1, unit cup.
        ops: Edits on the staged entry; indices match episodic.openWork / workingMemory.draftLog.
        optionId: Id from episodic.lastSuggestionOptions to log a prior compose_suggestions option,
            then optional ops/items.

    In your reply, confirm what you are about to log. For restaurants, set brandOrVenue on items.
    """
    return jobs.new_entry(
        ctx["req"],
        items=[item.model_dump() for item in items] if items else None,
        ops=[op.model_dump() for op in ops] if ops else None,
        option_id=optionId,
        memory=ctx["memory"],
        proposals=ctx["proposals"],
    )


@tool(args_schema=ComposeSuggestionsArgs)
def compose_suggestions(
    drafts: list[DraftMeal],
    mealSlot: Optional[str] = None,
    venue: Optional[str] = None,
    budget: Optional[StatedBudget] = None,
    appetite: Optional[AppetiteLevel] = None,
    ctx: Ctx = None,
) -> dict[str, Any]:
    """Propose 2–3 concrete meal ideas for a slot (non-blocking; user logs later via new_entry + optionId).

    When to use: They want meal ideas, what to eat next, or a restaurant order that fits remaining
    macros. Use real portions (2 eggs, 1 cup rice, 1 tbsp dressing). Respect semantic.assistanceLevel
    — do not suggest in quiet unless they asked.

    When not to use: If they only ask what they ate or what's left, answer from the context pack
    in text without calling a tool.

    Do not write calorie or macro totals in chat; the harness computes totals.

    Args:
        drafts: 2–3 options; every item needs foodQuery, quantity, and unit as a sitting.
        mealSlot: Slot to size against when the user named one.
        venue: Restaurant or place, when relevant (also set brandOrVenue on draft items).
        budget: Explicit macro ceiling up to remaining; overrides the guide when set.
        appetite: light, normal, or hearty from how much they want to eat; omit for normal.

    In your reply, name options in plain language and tie them to what's left today. Warm and
    specific beats one-word answers. semantic.slotBudgets are guides; set appetite from intent or
    pass budget up to semantic.remaining. Prefer variety; avoid repeating semantic.todayFamilies.
    """
    del venue
    from agent.harness.meal_budget import normalize_appetite

    return jobs.compose_suggestions(
        ctx["req"],
        meal_slot=mealSlot,
        budget=budget.model_dump() if budget else None,
        appetite=normalize_appetite(appetite),
        drafts=[draft.model_dump() for draft in drafts],
        memory=ctx["memory"],
        proposals=ctx["proposals"],
    )


@tool(args_schema=RepeatPriorMealArgs)
def repeat_prior_meal(entryIds: list[str], ctx: Ctx = None) -> dict[str, Any]:
    """Copy existing diary rows into the confirm sheet without re-searching foods.

    When to use: They want the same meal again (repeat lunch, log that again).

    When not to use: If they only ask what they ate or what's left, answer from the context pack
    in text without calling a tool.

    Args:
        entryIds: Diary entry ids from semantic.today or previousDays in the pack.
    """
    return jobs.repeat_prior_meal(ctx["req"], list(entryIds))


@tool(args_schema=EditEntryArgs)
def edit_entry(
    entryId: str,
    itemIndex: int,
    op: Literal["set_amount", "replace", "remove"],
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    item: Optional[ItemDraft] = None,
    ctx: Ctx = None,
) -> dict[str, Any]:
    """Change one line on an already-logged meal (HITL confirm_correction).

    When to use: They correct a logged item (amount, swap, remove one line) — not for staging a
    brand-new meal (use new_entry).

    When not to use: If they only ask what they ate or what's left, answer from the context pack
    in text without calling a tool.

    Args:
        entryId: Diary entry to change (from the pack).
        itemIndex: Item index inside that entry.
        op: set_amount, replace, or remove.
        quantity: New amount when op is set_amount.
        unit: Unit for the new amount.
        item: Replacement food when op is replace.
    """
    return jobs.edit_entry(
        ctx["req"],
        entry_id=entryId,
        item_index=itemIndex,
        op=op,
        quantity=quantity,
        unit=unit,
        item=item.model_dump() if item else None,
    )


@tool(args_schema=DeleteEntryArgs)
def delete_entry(entryId: str, dayKey: Optional[str] = None, ctx: Ctx = None) -> dict[str, Any]:
    """Stage removal of a whole logged entry (HITL confirm_delete) before Firestore delete.

    When to use: They want to delete an entire meal entry, not edit one line (use edit_entry).

    When not to use: If they only ask what they ate or what's left, answer from the context pack
    in text without calling a tool.

    Args:
        entryId: Diary entry id from the context pack.
        dayKey: Day YYYY-MM-DD when the entry is not on today in the pack.
    """
    return jobs.delete_entry(ctx["req"], entry_id=entryId, day_key=dayKey)


@tool(args_schema=SaveMemoryArgs)
def save_memory(
    op: Literal["add", "remove"],
    text: Optional[str] = None,
    noteId: Optional[str] = None,
    ctx: Ctx = None,
) -> dict[str, Any]:
    """Add or remove a long-term memory note (client applies memoryProposals).

    When to use: They state a durable preference or fact, or ask to forget a note. May accompany
    any other tool in the same turn.

    When not to use: If they only ask what they ate or what's left, answer from the context pack
    in text without calling a tool.

    Args:
        op: add a note or remove one by id.
        text: Note text when adding.
        noteId: Existing note id when removing (from longTerm.notes in the pack).
    """
    proposal = memory_proposal(op, text, noteId)
    if proposal is None:
        return {"error": "bad_args", "message": "save_memory needs add+text or remove+noteId"}
    ctx["proposals"].append(proposal)
    return {"kind": "memory"}


def _kind(lc: BaseTool, kind: Kind) -> BaseTool:
    lc.metadata = {**(lc.metadata or {}), "kind": kind}
    return lc


CAPY_TOOLS: list[BaseTool] = [
    _kind(new_entry, "primary"),
    _kind(compose_suggestions, "suggestions"),
    _kind(repeat_prior_meal, "primary"),
    _kind(edit_entry, "primary"),
    _kind(delete_entry, "primary"),
    _kind(save_memory, "memory"),
]

TOOLS_BY_NAME = {tool.name: tool for tool in CAPY_TOOLS}

TOOL_DECLARATIONS = [_declaration(tool) for tool in CAPY_TOOLS]


def parse_tool_args(name: str, arguments: dict[str, Any]) -> tuple[BaseTool, dict[str, Any]] | str:
    lc = TOOLS_BY_NAME.get(name)
    if lc is None:
        return f"unknown tool {name}"
    schema = lc.args_schema
    if schema is None:
        return f"tool {name} missing args_schema"
    try:
        parsed = schema.model_validate(arguments)
    except ValidationError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001
        return str(exc)
    payload = parsed.model_dump() if isinstance(parsed, BaseModel) else dict(parsed)
    return lc, payload


def validate_calls(calls: list[dict[str, Any]]) -> str | None:
    if not calls:
        return None
    for call in calls:
        parsed = parse_tool_args(str(call.get("name") or ""), call.get("arguments") or {})
        if isinstance(parsed, str):
            return parsed
    return None
