"""MCP server exposing Cappy meal-agent Cloud Functions as tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from capy_mcp.client import CallableClient

mcp = FastMCP(
    "capy-meal-agent",
    instructions=(
        "Tools for the Cappy meal agent: interpret utterances, log meals, "
        "sync profile, and read/update conversation threads. Requires CAPY_ACCESS_TOKEN "
        "or CAPY_FIREBASE_ID_TOKEN in the environment."
    ),
)

_client: CallableClient | None = None


def _client() -> CallableClient:
    global _client
    if _client is None:
        _client = CallableClient()
    return _client


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.tool(
    name="interpret_meal",
    description=(
        "Run the meal agent on an utterance (log, suggest, correct, clarify). "
        "Uses server Firestore context when use_server_context is true."
    ),
)
async def interpret_meal(
    utterance: str,
    day_key: str,
    timezone: str = "UTC",
    thread_id: str = "default",
    use_server_context: bool = True,
) -> str:
    payload: dict[str, Any] = {
        "utterance": utterance,
        "dayKey": day_key,
        "timezone": timezone,
        "threadId": thread_id,
        "useServerContext": use_server_context,
    }
    result = await _client().call("interpret_meal", payload, timeout=120.0)
    return _json(result)


@mcp.tool(
    name="log_meal",
    description="Write a confirmed meal to the user's diary (Firestore).",
)
async def log_meal(
    day_key: str,
    meal_slot: str,
    items: list[dict[str, Any]],
    entry_id: str | None = None,
    client_mutation_id: str | None = None,
    confirmed: bool = True,
) -> str:
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
    return _json(await _client().call("log_meal", payload))


@mcp.tool(
    name="patch_profile",
    description=(
        "Merge profile fields: timezone, dailyTarget, mealPlan, likes, dislikes, "
        "allergies, diets, assistanceLevel, responseStyle, longTermMemory."
    ),
)
async def patch_profile(patch: dict[str, Any]) -> str:
    return _json(await _client().call("patch_profile", patch))


@mcp.tool(
    name="get_thread",
    description=(
        "Fetch a paginated slice of Capy chat history (newest page without cursor; "
        "pass cursor from pageInfo.nextCursor for older messages)."
    ),
)
async def get_thread(
    thread_id: str = "default",
    limit: int = 12,
    cursor: str | None = None,
) -> str:
    payload: dict[str, Any] = {"threadId": thread_id, "limit": limit}
    if cursor:
        payload["cursor"] = cursor
    return _json(await _client().call("get_thread", payload))


@mcp.tool(
    name="patch_thread",
    description="Append an assistant message or record a day-rollover note on the thread.",
)
async def patch_thread(
    assistant_text: str | None = None,
    thread_id: str = "default",
    clear_working_memory: bool = False,
    previous_day_key: str | None = None,
    meal_count: int | None = None,
) -> str:
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
    return _json(await _client().call("patch_thread", payload))


@mcp.tool(
    name="exchange_access_token",
    description=(
        "Exchange a Firebase ID token for a short-lived Cappy access token (1h). "
        "Use when the MCP host only has a Firebase login, not CAPY_ACCESS_TOKEN."
    ),
)
async def exchange_access_token(firebase_id_token: str) -> str:
    client = CallableClient(access_token=firebase_id_token)
    return _json(await client.exchange_access_token(firebase_id_token))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
