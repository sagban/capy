"""Bearer gate for the Streamable HTTP mount at /mcp."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from agent.auth import AuthError, resolve_bearer_to_uid
from agent.request_context import current_uid


def _bearer_from_headers(headers: dict[str, str]) -> str | None:
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def _send_json_error(send: Any, status: int, detail: str) -> None:
    body = json.dumps({"error": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class AuthMcpMiddleware:
    """ASGI middleware: Bearer auth and uid context for /mcp."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        token = _bearer_from_headers(headers)
        if not token:
            await _send_json_error(send, 401, "Sign in required.")
            return
        try:
            uid = resolve_bearer_to_uid(token)
        except AuthError as exc:
            await _send_json_error(send, 401, str(exc))
            return
        reset = current_uid.set(uid)
        try:
            await self.app(scope, receive, send)
        finally:
            current_uid.reset(reset)
