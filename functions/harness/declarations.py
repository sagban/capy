"""Tools the model may call. Search, scale, and web nutrition stay inside the executors."""

from __future__ import annotations

from typing import Any

_ITEM = {
    "type": "object",
    "properties": {
        "rawText": {"type": "string"},
        "foodQuery": {"type": "string"},
        "brandOrVenue": {"type": "string"},
        "quantity": {"type": "number"},
        "unit": {"type": "string"},
        "aliases": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["foodQuery"],
}

_DRAFT_ITEM = {
    "type": "object",
    "properties": {
        "foodQuery": {"type": "string"},
        "quantity": {"type": "number"},
        "unit": {"type": "string"},
        "brandOrVenue": {"type": "string"},
        "aliases": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["foodQuery", "quantity", "unit"],
}

TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "resolve_meal",
        "description": "Resolve foods the user wants to log. Omit quantity when they did not say how much.",
        "parameters": {
            "type": "object",
            "properties": {"items": {"type": "array", "items": _ITEM}},
            "required": ["items"],
        },
    },
    {
        "name": "edit_draft",
        "description": "Edit the open confirm draft: set_amount, remove, add, or replace.",
        "parameters": {
            "type": "object",
            "properties": {
                "ops": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {"type": "string"},
                            "index": {"type": "integer"},
                            "quantity": {"type": "number"},
                            "unit": {"type": "string"},
                            "item": _ITEM,
                        },
                        "required": ["op"],
                    },
                }
            },
            "required": ["ops"],
        },
    },
    {
        "name": "log_from_suggestion",
        "description": "Copy a stored suggestion option into the confirm sheet, with optional edits.",
        "parameters": {
            "type": "object",
            "properties": {
                "optionId": {"type": "string"},
                "ops": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["optionId"],
        },
    },
    {
        "name": "compose_suggestions",
        "description": "Suggest meals. Every item needs your recommended quantity and unit. Pass budget only if the user stated one.",
        "parameters": {
            "type": "object",
            "properties": {
                "mealSlot": {"type": "string"},
                "venue": {"type": "string"},
                "budget": {
                    "type": "object",
                    "properties": {
                        "calories": {"type": "number"},
                        "proteinG": {"type": "number"},
                    },
                },
                "drafts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "items": {"type": "array", "items": _DRAFT_ITEM},
                        },
                        "required": ["title", "items"],
                    },
                },
            },
            "required": ["drafts"],
        },
    },
    {
        "name": "repeat_prior_meal",
        "description": "Copy diary entries by entryId into the confirm sheet. Do not re-search them.",
        "parameters": {
            "type": "object",
            "properties": {"entryIds": {"type": "array", "items": {"type": "string"}}},
            "required": ["entryIds"],
        },
    },
    {
        "name": "correct_entry",
        "description": "Correct one diary item by entryId and itemIndex.",
        "parameters": {
            "type": "object",
            "properties": {
                "entryId": {"type": "string"},
                "itemIndex": {"type": "integer"},
                "op": {"type": "string"},
                "quantity": {"type": "number"},
                "unit": {"type": "string"},
                "item": _ITEM,
            },
            "required": ["entryId", "itemIndex", "op"],
        },
    },
    {
        "name": "accept_option",
        "description": "Accept an open clarify chip by its id. Use this when the user agrees with the portion or food already shown. Do not invent grams.",
        "parameters": {
            "type": "object",
            "properties": {"optionId": {"type": "string"}},
            "required": ["optionId"],
        },
    },
    {
        "name": "lookup_menu",
        "description": "Restaurant menu names only. Call at most once, before compose_suggestions.",
        "parameters": {
            "type": "object",
            "properties": {"venue": {"type": "string"}},
            "required": ["venue"],
        },
    },
    {
        "name": "save_memory",
        "description": "Add or remove a long-term memory note. Can accompany any other tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "op": {"type": "string"},
                "text": {"type": "string"},
                "noteId": {"type": "string"},
            },
            "required": ["op"],
        },
    },
]
