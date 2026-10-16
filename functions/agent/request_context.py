"""Per-request uid for MCP tool handlers (set by HTTP auth middleware)."""

from __future__ import annotations

import contextvars

current_uid: contextvars.ContextVar[str | None] = contextvars.ContextVar("capy_uid", default=None)


def require_uid() -> str:
    uid = current_uid.get()
    if not uid:
        raise PermissionError("Sign in required.")
    return uid
