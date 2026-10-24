"""Cloud Run ASGI entry: health, token exchange, and MCP Streamable HTTP at /mcp/."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse
from firebase_admin import initialize_app

from agent.auth import AuthError, exchange_firebase_for_access, resolve_bearer_to_uid
from agent.live_session import run_live_websocket
from agent.request_context import current_uid
from cloudrun.authenticate import register_authenticate
from cloudrun.mcp import AuthMcpMiddleware, mcp, mcp_http_asgi

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


app = FastAPI(title="Capy API", version="1.0", lifespan=_lifespan)


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


register_authenticate(app)


@app.post("/exchange_access_token")
async def http_exchange_access_token(request: Request) -> JSONResponse:
    raw = await _read_payload(request)
    try:
        return JSONResponse(_callable_envelope(exchange_firebase_for_access(raw)))
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _bearer_from_websocket(ws: WebSocket) -> str | None:
    auth = ws.headers.get("authorization") or ws.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    token = (ws.query_params.get("token") or "").strip()
    return token or None


@app.websocket("/v1/live")
async def websocket_live(ws: WebSocket) -> None:
    token = _bearer_from_websocket(ws)
    if not token:
        await ws.close(code=4401, reason="Sign in required.")
        return
    try:
        uid = resolve_bearer_to_uid(token)
    except AuthError as exc:
        await ws.close(code=4401, reason=str(exc))
        return

    await ws.accept()
    reset = current_uid.set(uid)
    try:
        await run_live_websocket(ws, uid=uid)
    finally:
        current_uid.reset(reset)
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


# Streamable HTTP (spec 2025-11-25): POST/GET /mcp/ with Authorization: Bearer.
app.mount("/mcp", AuthMcpMiddleware(_mcp_asgi))
