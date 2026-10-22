"""Cloud Run ASGI entry: health, token exchange, and MCP Streamable HTTP at /mcp/."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from firebase_admin import initialize_app

from agent.auth import AuthError, exchange_firebase_for_access, resolve_bearer_to_uid
from agent.kitchen_session import register_kitchen
from agent.mcp_host import mcp, mcp_http_asgi
from agent.request_context import current_uid

try:
    initialize_app()
except ValueError:
    pass

_mcp_asgi = mcp_http_asgi()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Streamable HTTP rejects every request until this task group is running.
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Cappy API", version="1.0", lifespan=_lifespan)


def _bearer_from_headers(headers: dict[str, str]) -> str | None:
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def _read_payload(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        return {}
    if "data" in body and isinstance(body["data"], dict):
        return body["data"]
    return body


def _callable_envelope(result: Any) -> dict[str, Any]:
    return {"result": result}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


register_kitchen(app)


@app.post("/exchange_access_token")
async def http_exchange_access_token(request: Request) -> JSONResponse:
    raw = await _read_payload(request)
    try:
        return JSONResponse(_callable_envelope(exchange_firebase_for_access(raw)))
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


class _AuthMcpMiddleware:
    """ASGI middleware: Bearer auth + uid context for /mcp."""

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


# Streamable HTTP (spec 2025-11-25): POST/GET /mcp/ with Authorization: Bearer.
app.mount("/mcp", _AuthMcpMiddleware(_mcp_asgi))
