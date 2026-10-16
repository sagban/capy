"""LangChain @tool functions and their argument models."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from langchain_core.tools import BaseTool, InjectedToolArg, tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field, ValidationError, model_validator

from schemas import ItemDraft
from agent.harness.tools.common import memory_proposal
from agent.harness.tools import jobs

Kind = Literal["primary", "suggestions", "memory", "lookup"]
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


class DraftOp(BaseModel):
    op: Literal["set_amount", "remove", "add", "replace"]
    index: Optional[int] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    item: Optional[ItemDraft] = None


class ResolveMealArgs(BaseModel):
    items: list[ItemDraft] = Field(min_length=1)


class EditDraftArgs(BaseModel):
    ops: list[DraftOp] = Field(min_length=1)


class LogFromSuggestionArgs(BaseModel):
    optionId: str
    ops: list[DraftOp] = Field(default_factory=list)


class ComposeSuggestionsArgs(BaseModel):
    drafts: list[DraftMeal] = Field(min_length=1)
    mealSlot: Optional[str] = None
    venue: Optional[str] = None
    budget: Optional[StatedBudget] = None


class RepeatPriorMealArgs(BaseModel):
    entryIds: list[str] = Field(min_length=1)


class CorrectEntryArgs(BaseModel):
    entryId: str
    itemIndex: int
    op: Literal["set_amount", "replace", "remove"]
    quantity: Optional[float] = None
    unit: Optional[str] = None
    item: Optional[ItemDraft] = None


class LookupMenuArgs(BaseModel):
    venue: str


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


@tool(args_schema=ResolveMealArgs)
def resolve_meal(items: list[ItemDraft], ctx: Ctx = None) -> dict[str, Any]:
    """Log foods the user said they ate. Opens the confirm sheet.

    Args:
        items: Foods to resolve. Omit quantity when they did not say how much.
    """
    return jobs.resolve_meal(
        ctx["req"],
        [item.model_dump() for item in items],
        memory=ctx["memory"],
        proposals=ctx["proposals"],
    )


@tool(args_schema=EditDraftArgs)
def edit_draft(ops: list[DraftOp], ctx: Ctx = None) -> dict[str, Any]:
    """Edit the open confirm draft.

    Args:
        ops: Ordered edits against draftLog or resolveQueue in the pack.
    """
    return jobs.edit_draft(ctx["req"], [op.model_dump() for op in ops])


@tool(args_schema=LogFromSuggestionArgs)
def log_from_suggestion(
    optionId: str,
    ops: list[DraftOp] | None = None,
    ctx: Ctx = None,
) -> dict[str, Any]:
    """Copy a stored suggestion into the confirm sheet.

    Args:
        optionId: Id from lastSuggestionOptions in the pack (opt1, opt2, …).
        ops: Optional edits after copying.
    """
    dumped = [op.model_dump() for op in ops] if ops else None
    return jobs.log_from_suggestion(ctx["req"], optionId, dumped, memory=ctx["memory"])


@tool(args_schema=ComposeSuggestionsArgs)
def compose_suggestions(
    drafts: list[DraftMeal],
    mealSlot: Optional[str] = None,
    venue: Optional[str] = None,
    budget: Optional[StatedBudget] = None,
    ctx: Ctx = None,
) -> dict[str, Any]:
    """Draft 2 or 3 different meals for the slot they asked for. Do not write calorie or macro totals.

    Args:
        drafts: Meal options. Every item needs foodQuery, quantity, and unit as a sitting.
        mealSlot: Slot to size against when the user named one.
        venue: Restaurant or place, when relevant.
        budget: Calories/protein only if the user stated a budget.
    """
    del venue
    return jobs.compose_suggestions(
        ctx["req"],
        meal_slot=mealSlot,
        budget=budget.model_dump() if budget else None,
        drafts=[draft.model_dump() for draft in drafts],
        memory=ctx["memory"],
        proposals=ctx["proposals"],
    )


@tool(args_schema=RepeatPriorMealArgs)
def repeat_prior_meal(entryIds: list[str], ctx: Ctx = None) -> dict[str, Any]:
    """Copy diary entries into the confirm sheet. Do not re-search them.

    Args:
        entryIds: Diary entry ids from the pack.
    """
    return jobs.repeat_prior_meal(ctx["req"], list(entryIds))


@tool(args_schema=CorrectEntryArgs)
def correct_entry(
    entryId: str,
    itemIndex: int,
    op: Literal["set_amount", "replace", "remove"],
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    item: Optional[ItemDraft] = None,
    ctx: Ctx = None,
) -> dict[str, Any]:
    """Correct one diary item by entryId and itemIndex.

    Args:
        entryId: Diary entry to change.
        itemIndex: Item index inside that entry.
        op: set_amount, replace, or remove.
        quantity: New amount when op is set_amount.
        unit: Unit for the new amount.
        item: Replacement food when op is replace.
    """
    return jobs.correct_entry(
        ctx["req"],
        entry_id=entryId,
        item_index=itemIndex,
        op=op,
        quantity=quantity,
        unit=unit,
        item=item.model_dump() if item else None,
    )


@tool(args_schema=LookupMenuArgs)
def lookup_menu(venue: str, ctx: Ctx = None) -> dict[str, Any]:
    """Restaurant menu names only. Ignore any numbers.

    Args:
        venue: Restaurant or chain to look up.
    """
    del ctx
    return jobs.fetch_menu(venue)


@tool(args_schema=SaveMemoryArgs)
def save_memory(
    op: Literal["add", "remove"],
    text: Optional[str] = None,
    noteId: Optional[str] = None,
    ctx: Ctx = None,
) -> dict[str, Any]:
    """Add or remove a long-term memory note. Can accompany any other tool.

    Args:
        op: add a note or remove one by id.
        text: Note text when adding.
        noteId: Existing note id when removing.
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
    _kind(resolve_meal, "primary"),
    _kind(edit_draft, "primary"),
    _kind(log_from_suggestion, "primary"),
    _kind(compose_suggestions, "suggestions"),
    _kind(repeat_prior_meal, "primary"),
    _kind(correct_entry, "primary"),
    _kind(lookup_menu, "lookup"),
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
