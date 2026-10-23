"""Hosted MCP server: tool surface and the bearer gate on /mcp."""

from cloudrun.mcp.host import mcp, mcp_http_asgi
from cloudrun.mcp.http import AuthMcpMiddleware

__all__ = ["AuthMcpMiddleware", "mcp", "mcp_http_asgi"]
