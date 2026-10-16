# Cappy MCP server

Stdio MCP server that wraps Firebase Callable functions for the meal agent harness.

## Hosted MCP (Cloud Run)

For demo / personal use, MCP is also served from the **`cappy-api`** Cloud Run service (with `/healthz` and `/exchange_access_token` only besides MCP):

```text
https://<cappy-api-url>/mcp/sse
```

Bearer auth required. See [docs/architecture/alexa-setup.md](../docs/architecture/alexa-setup.md) and [deploy/README.md](../deploy/README.md).

## Auth (local stdio)

Set **one** of:

| Variable | Use |
|----------|-----|
| `CAPY_ACCESS_TOKEN` | Short-lived JWT from `exchange_access_token` (recommended for MCP) |
| `CAPY_FIREBASE_ID_TOKEN` | Firebase ID token (refresh manually or via host) |

Optional: `CAPY_PROJECT_ID` (default `capy-dogfood`), `CAPY_FUNCTIONS_REGION` (`us-central1`), `CAPY_FUNCTIONS_EMULATOR_HOST` (`127.0.0.1:5001`).

Flow for long-running MCP hosts:

1. Sign in with Firebase Auth (email/password, Google, etc.) in a trusted environment.
2. Call MCP tool `exchange_access_token` or the `exchange_access_token` callable with `firebaseIdToken`.
3. Set `CAPY_ACCESS_TOKEN` to the returned `accessToken` (valid 1 hour).

See [docs/architecture/external-auth.md](../docs/architecture/external-auth.md).

## Run

```bash
cd mcp_server
pip install -r requirements.txt
CAPY_ACCESS_TOKEN=... CAPY_FUNCTIONS_EMULATOR_HOST=127.0.0.1:5001 \
  python -m capy_mcp.server
```

Cursor / Claude Desktop config (example):

```json
{
  "mcpServers": {
    "capy": {
      "command": "python",
      "args": ["-m", "capy_mcp.server"],
      "cwd": "/path/to/capy/mcp_server",
      "env": {
        "CAPY_ACCESS_TOKEN": "<token>",
        "CAPY_FUNCTIONS_EMULATOR_HOST": "127.0.0.1:5001"
      }
    }
  }
}
```

## Tools

| Tool | Callable | Purpose |
|------|----------|---------|
| `interpret_meal` | `interpret_meal` | Agent turn (suggestions, confirm, clarify) |
| `log_meal` | `log_meal` | Persist a meal entry |
| `patch_profile` | `patch_profile` | Update prefs / targets / meal plan |
| `get_thread` | `get_thread` | Paginated chat history |
| `patch_thread` | `patch_thread` | Assistant line / day rollover |
| `exchange_access_token` | `exchange_access_token` | Mint access JWT from Firebase ID token |
