"""MCP tool surface for hosted SSE (five meal-agent tools)."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from agent.request_context import require_uid
from interpret_api import interpret_meal_for_uid
from firebase_functions import https_fn

from user_api import (
    get_thread_for_uid,
    log_meal_for_uid,
    patch_profile_for_uid,
    patch_thread_for_uid,
)


def _invoke(handler, uid: str, payload: dict[str, Any]) -> Any:
    try:
        return handler(uid, payload)
    except https_fn.HttpsError as exc:
        raise ValueError(exc.message) from exc

mcp = FastMCP(
    "capy-meal-agent",
    instructions=(
        "Cappy meal agent: interpret utterances, log meals, sync profile, "
        "and paginate conversation threads. Requires Authorization: Bearer on the MCP HTTP session."
    ),
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.tool(
    name="interpret_meal",
    description="Run the meal agent on an utterance (log, suggest, correct, clarify).",
)
async def interpret_meal(
    utterance: str,
    day_key: str,
    timezone: str = "UTC",
    thread_id: str = "default",
    use_server_context: bool = True,
) -> str:
    uid = require_uid()
    payload: dict[str, Any] = {
        "utterance": utterance,
        "dayKey": day_key,
        "timezone": timezone,
        "threadId": thread_id,
        "useServerContext": use_server_context,
    }
    return _json(interpret_meal_for_uid(uid, payload))


@mcp.tool(name="log_meal", description="Write a confirmed meal to the user's diary.")
async def log_meal(
    day_key: str,
    meal_slot: str,
    items: list[dict[str, Any]],
    entry_id: str | None = None,
    client_mutation_id: str | None = None,
    confirmed: bool = True,
) -> str:
    uid = require_uid()
    payload: dict[str, Any] = {
        "dayKey": day_key,
        "mealSlot": meal_slot,
        "items": items,
        "confirmed": confirmed,
    }
    if entry_id:
        payload["entryId"] = entry_id
    if client_mutation_id:
        payload["clientMutationId"] = client_mutation_id
    return _json(_invoke(log_meal_for_uid, uid, payload))


@mcp.tool(name="patch_profile", description="Merge profile fields on users/{uid}.")
async def patch_profile(patch: dict[str, Any]) -> str:
    uid = require_uid()
    return _json(_invoke(patch_profile_for_uid, uid, patch))


@mcp.tool(name="get_thread", description="Paginated Capy chat history.")
async def get_thread(
    thread_id: str = "default",
    limit: int = 12,
    cursor: str | None = None,
) -> str:
    uid = require_uid()
    payload: dict[str, Any] = {"threadId": thread_id, "limit": limit}
    if cursor:
        payload["cursor"] = cursor
    return _json(_invoke(get_thread_for_uid, uid, payload))


@mcp.tool(name="patch_thread", description="Append assistant text or day-rollover note.")
async def patch_thread(
    assistant_text: str | None = None,
    thread_id: str = "default",
    clear_working_memory: bool = False,
    previous_day_key: str | None = None,
    meal_count: int | None = None,
) -> str:
    uid = require_uid()
    payload: dict[str, Any] = {"threadId": thread_id}
    if assistant_text:
        payload["assistantText"] = assistant_text
    if clear_working_memory:
        payload["clearWorkingMemory"] = True
    if previous_day_key is not None and meal_count is not None:
        payload["dayRollover"] = {
            "previousDayKey": previous_day_key,
            "mealCount": meal_count,
        }
    return _json(_invoke(patch_thread_for_uid, uid, payload))


def mcp_sse_asgi():
    """Starlette ASGI app for MCP over SSE (mount at /mcp)."""
    if hasattr(mcp, "sse_app"):
        return mcp.sse_app()
    if hasattr(mcp, "streamable_http_app"):
        return mcp.streamable_http_app()
    raise RuntimeError("Installed mcp package lacks sse_app(); upgrade mcp>=1.2")
