"""Cloud Run ASGI entry: health, token exchange, and MCP Streamable HTTP at /mcp/."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from firebase_admin import initialize_app

from agent.auth import AuthError, exchange_firebase_for_access
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


# Streamable HTTP (spec 2025-11-25): POST/GET /mcp/ with Authorization: Bearer.
app.mount("/mcp", AuthMcpMiddleware(_mcp_asgi))
