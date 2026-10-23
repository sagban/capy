"""MCP tool surface for hosted Streamable HTTP (spec 2025-11-25)."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from firebase_functions import https_fn

from agent.request_context import require_uid

from agent.tools.diary_io import delete_meal as remove_meal
from agent.tools.diary_io import get_diary_for_uid
from agent.tools.diary_io import write_food_entry
from agent.tools.lookups import lookup_barcode as barcode_lookup
from agent.tools.lookups import search_catalog as catalog_search
from agent.tools.lookups import search_library as library_search
from agent.tools.lookups import search_usda as usda_search
from agent.tools.portion import portion_to_grams as grams_for_portion
from agent.user_store import library_refs_for_interpret
from user_api import (
    delete_library_item_for_uid,
    list_library_for_uid,
    patch_profile_for_uid,
    upsert_library_item_for_uid,
)


def _invoke(handler, uid: str, payload: dict[str, Any]) -> Any:
    try:
        return handler(uid, payload)
    except https_fn.HttpsError as exc:
        raise ValueError(exc.message) from exc

mcp = FastMCP(
    "capy-meal-agent",
    instructions=(
        "Capy tools for an external agent: look up foods, write a food, recipe, or meal to the diary, and sync profile and library. "
        "search_catalog, search_usda, search_library, and lookup_barcode return hits and do not log. "
        "Requires Authorization: Bearer on the MCP HTTP session."
    ),
    # Mounted at /mcp, so the Streamable HTTP endpoint is POST/GET {host}/mcp/.
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
    # Bearer auth is the gate. The SDK's default host check only allows localhost.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _written(result: dict[str, Any]) -> str:
    if result.get("error"):
        raise ValueError(str(result.get("message") or result["error"]))
    return _json(result)


@mcp.tool(name="write_food_entry")
async def write_food_entry_tool(
    day_key: str,
    meal_slot: str,
    kind: str,
    name: str,
    grams: float,
    per100g: dict[str, Any],
    foodId: str | None = None,
    source: str | None = None,
    ingredientFamily: str | None = None,
    citationUrl: str | None = None,
    entry_id: str | None = None,
    client_mutation_id: str | None = None,
    confirmed: bool = True,
) -> str:
    """Write one diary entry: a food, a recipe, or a meal.

    When to use: You already looked up this one thing, called portion_to_grams, and the user
    agreed. One call writes one entry. kind is food, recipe, or meal. Pass name, grams,
    foodId, and source from that hit. per100g is calories, proteinG, carbsG, and fatG for
    100 grams of this entry, copied unchanged. The diary multiplies by grams/100. Another
    food is another call. Pass entry_id to replace one existing entry. Pass the same
    client_mutation_id on a retry so the write happens once.

    When not to use: You have not looked it up. Do not pass several foods. Do not invent
    grams or per100g numbers. Saving a reusable library row is upsert_library_item.

    Args:
        day_key: Diary day, YYYY-MM-DD.
        meal_slot: Slot name from the user's meal plan.
        kind: food, recipe, or meal.
        name: Name of this one entry.
        grams: Portion weight in grams.
        per100g: Calories and macros for 100 grams, copied from the lookup hit.
        entry_id: Existing entry to update. Omit to create one.
        client_mutation_id: Idempotency key for this write.
        confirmed: Defaults to true. A confirmed row counts in the day's totals.
    """
    uid = require_uid()
    return _written(
        write_food_entry(
            uid,
            day_key,
            meal_slot,
            kind,
            name,
            grams,
            per100g,
            foodId=foodId,
            source=source,
            ingredientFamily=ingredientFamily,
            citationUrl=citationUrl,
            entry_id=entry_id,
            client_mutation_id=client_mutation_id,
            confirmed=confirmed,
        )
    )


@mcp.tool(name="get_diary")
async def get_diary(day_key: str) -> str:
    """Read one day's diary entries and remaining macros.

    When to use: You need entry ids and the current items before an edit, a delete, or a suggestion.
    When not to use: You already have those rows from this turn.

    Args:
        day_key: Diary day, YYYY-MM-DD.
    """
    uid = require_uid()
    return _json(get_diary_for_uid(uid, day_key))


@mcp.tool(name="search_catalog")
async def search_catalog(query: str, limit: int = 10) -> str:
    """Look up a generic food in the bundled seed catalog.

    When to use: The user named a staple or a common food and you need per-100g numbers and measures.
    When not to use: A barcode, a saved library title, or a meal you are ready to write. This does not log.

    Args:
        query: Food name, such as rice, egg, or paneer.
        limit: Maximum hits to return. Defaults to 10.
    """
    require_uid()
    return _json(catalog_search(query, limit))


@mcp.tool(name="search_usda")
async def search_usda(query: str, limit: int = 8) -> str:
    """Fetch foods from USDA FoodData Central.

    When to use: The catalog missed, or the user named a branded package.
    When not to use: A staple you expect in the catalog, a barcode, or a write. This does not log.

    Args:
        query: Food name to fetch.
        limit: Maximum hits to return. Defaults to 8.
    """
    require_uid()
    return _json(usda_search(query, limit))


@mcp.tool(name="search_library")
async def search_library(query: str, limit: int = 3) -> str:
    """Match a name against the signed-in user's saved library.

    When to use: They used a personal title ("Gym Bowl") and you need that saved row.
    When not to use: A generic staple, a brand that is not saved, or a barcode. This does not log.
    A single generic word does not match a longer saved title. To list or edit the library, use list_library.

    Args:
        query: Saved food, recipe, or meal title.
        limit: Maximum hits to return. Defaults to 3.
    """
    uid = require_uid()
    return _json(library_search(query, library_refs_for_interpret(uid), limit))


@mcp.tool(name="lookup_barcode")
async def lookup_barcode(gtin: str) -> str:
    """Look up one package barcode on Open Food Facts.

    When to use: The user gave a UPC or EAN.
    When not to use: You have a food name and no barcode. A miss is found false. Do not fill in macros.

    Args:
        gtin: Barcode digits.
    """
    require_uid()
    return _json(barcode_lookup(gtin))


@mcp.tool(name="portion_to_grams")
async def portion_to_grams(
    quantity: float,
    unit: str,
    measures: list[dict[str, Any]] | None = None,
) -> str:
    """Turn a quantity and unit into grams using the hit's measures.

    When to use: You chose a hit and the user named how much. Pass that hit's measures through unchanged.
    When not to use: You do not have a hit yet. Call a lookup first. An unknown unit returns unmapped true.

    Args:
        quantity: How many of the unit the user said.
        unit: Unit the user said, such as cup, large, or g.
        measures: Household measures from the hit you chose.
    """
    require_uid()
    return _json(grams_for_portion(quantity, unit, measures))


@mcp.tool(name="delete_food_entry")
async def delete_food_entry(
    day_key: str,
    entry_id: str,
    client_mutation_id: str | None = None,
) -> str:
    """Delete one diary entry.

    When to use: The user wants that whole entry gone and you have its entry id.
    When not to use: The entry should change. Call write_food_entry with entry_id and the new fields.

    Args:
        day_key: Diary day, YYYY-MM-DD.
        entry_id: Entry to delete.
        client_mutation_id: Idempotency key for this delete.
    """
    uid = require_uid()
    return _written(
        remove_meal(uid, day_key, entry_id, client_mutation_id=client_mutation_id)
    )


@mcp.tool(name="patch_profile")
async def patch_profile(patch: dict[str, Any]) -> str:
    """Merge profile fields for the signed-in user.

    When to use: The user changed a durable setting: timezone, dailyTarget, mealPlan, likes,
    dislikes, allergies, diets, assistanceLevel, responseStyle, or longTermMemory. Send only
    the keys that changed.

    When not to use: They are logging food. Use a lookup, portion_to_grams, and
    write_food_entry. They are saving or removing a library food — call the library tools. Do not put
    a meal entry in this patch.

    Args:
        patch: Partial profile object. Only timezone, dailyTarget, mealPlan, likes, dislikes,
            allergies, diets, assistanceLevel, responseStyle, and longTermMemory are kept.
            Other keys are ignored.
    """
    uid = require_uid()
    return _json(_invoke(patch_profile_for_uid, uid, patch))


@mcp.tool(name="upsert_library_item")
async def upsert_library_item(item: dict[str, Any], client_mutation_id: str | None = None) -> str:
    """Create or replace one saved library food, recipe, or meal.

    When to use: The user wants a reusable item in their library. Call list_library first
    when you need an existing id to replace. Pass the same client_mutation_id on a retry.

    When not to use: They ate something today. Look it up, call portion_to_grams, then
    write_food_entry. The library is not the diary.

    Args:
        item: Library row with name and kind (food, recipe, or meal). Include id to replace
            an existing row, plus macros and ingredients when you have them.
        client_mutation_id: Idempotency key for this write.
    """
    uid = require_uid()
    payload: dict[str, Any] = {"item": item}
    if client_mutation_id:
        payload["clientMutationId"] = client_mutation_id
    return _json(_invoke(upsert_library_item_for_uid, uid, payload))


@mcp.tool(name="delete_library_item")
async def delete_library_item(id: str, client_mutation_id: str | None = None) -> str:
    """Soft-delete one saved library item. The row stays, marked deleted.

    When to use: The user wants a library food, recipe, or meal removed. Take id from
    list_library or from the upsert that created it. Pass the same client_mutation_id on
    a retry.

    When not to use: They want today's diary entry removed. Call delete_food_entry with the entry id
    from get_diary. Do not guess an id.

    Args:
        id: Library item id.
        client_mutation_id: Idempotency key for this delete.
    """
    uid = require_uid()
    payload: dict[str, Any] = {"id": id}
    if client_mutation_id:
        payload["clientMutationId"] = client_mutation_id
    return _json(_invoke(delete_library_item_for_uid, uid, payload))


@mcp.tool(name="list_library")
async def list_library(include_deleted: bool = False) -> str:
    """List the signed-in user's saved library items.

    When to use: You need ids or names before upsert_library_item or delete_library_item,
    or the user asked what they have saved.

    When not to use: They asked what they ate today or what's left. Call get_diary.
    The diary is not the library. Leave include_deleted false unless they asked for
    removed items.

    Args:
        include_deleted: Include soft-deleted rows. Defaults to false.
    """
    uid = require_uid()
    return _json(_invoke(list_library_for_uid, uid, {"includeDeleted": include_deleted}))


def mcp_http_asgi():
    """Starlette ASGI app for MCP Streamable HTTP (spec 2025-11-25). Mount at /mcp.

    The parent ASGI app must run ``mcp.session_manager.run()`` in its lifespan.
    Clients POST JSON-RPC to ``/mcp/`` with ``Accept: application/json, text/event-stream``
    and ``Authorization: Bearer``.
    """
    if not hasattr(mcp, "streamable_http_app"):
        raise RuntimeError(
            "Installed mcp package lacks streamable_http_app(); upgrade to mcp>=1.12,<2."
        )
    return mcp.streamable_http_app()
