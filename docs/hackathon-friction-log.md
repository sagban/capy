# Capy friction log

Amazon Developer Hackathon, Alexa+ track. Three entries. Severity is Critical, High, or Medium.

## 1. Mount Streamable HTTP where the spec says to

**Task.** Expose the meal tools at one Streamable HTTP endpoint, spec 2025-11-25, so an Alexa+ client can call them.

**Steps.** Installed the MCP Python SDK. Followed the first server example, which mounts SSE at `/sse` and `/messages/`. Then switched to `streamable_http_app` and deployed the process to Cloud Run.

**Expected.** `POST /mcp/` with `Accept: application/json, text/event-stream` returns `protocolVersion` `2025-11-25`.

**Actual.** Every request failed with "Task group is not initialized" until the parent process ran `session_manager.run()` in the ASGI lifespan. After that, the default host check rejected the `Host` Cloud Run sends, because the default allow-list is localhost. `/mcp` without the trailing slash redirected instead of answering.

**Severity.** Critical.

**Workaround.** `stateless_http=True`, `json_response=True`, the lifespan hook, `TransportSecuritySettings(enable_dns_rebinding_protection=False)`, and the trailing slash. Bearer auth is the gate. The server is `functions/cloudrun/mcp/host.py`, mounted by `functions/cloudrun/app.py`.

**Suggestion.** Publish one getting-started page that mounts Streamable HTTP with bearer auth, names the `session_manager.run()` lifespan call, and marks SSE as legacy.

## 2. Install the SDK the existing server imports

**Task.** Install `mcp` on a clean machine and start the same server.

**Steps.** `pip install mcp` on a new virtualenv. Imported `FastMCP` the way `functions/cloudrun/mcp/host.py` does.

**Expected.** The current major version still exports `FastMCP`.

**Actual.** `mcp` 2.0 removed `FastMCP` and left no in-repo bridge. A fresh install breaks a server that already runs on 1.x.

**Severity.** High.

**Workaround.** Pin `mcp>=1.12,<2`. The host checks for `streamable_http_app` and tells you to upgrade into that range.

**Suggestion.** Keep `FastMCP` importable in 2.x, or ship a documented rename in the same release that removes it.

## 3. Hand Alexa a bearer for an account the person already has

**Task.** Link an Alexa skill to the Capy account and log one meal.

**Steps.** Opened the Alexa Developer Console account-linking fields: authorization URI, access token URI, Auth Code Grant, HTTP bearer. Compared that with the bearer `GET /authenticate` already mints for the phone and for MCP.

**Expected.** Alexa opens one authorize page for the account the person already uses, receives a bearer, and the skill backend presents that bearer to `POST /mcp/`. The link lasts longer than a cooking session.

**Actual.** The authorize page and token endpoint are a second login on top of Firebase Auth: client id, client secret, domain list, one-time code, redirect back to `alexa.amazon.com`. The sample path is a token pasted into the skill test Access Token field. It expires in 3600 seconds. A refresh token is optional. The console also makes it easy to point linking at MCP OAuth scopes. The skill should receive the bearer, and the skill backend should present it to MCP.

**Severity.** Critical.

**Workaround.** `GET /authenticate` signs in with the same email and password as the phone and returns a one-hour bearer plus an MCP config. That is what the demo uses. A kitchen that dies at minute 61 is not shipped.

**Suggestion.** Ship a minimal authorize page and token endpoint that return this same bearer for an existing account, with a refresh token. Document that linking is not MCP OAuth. Document how an Alexa+ client discovers a self-hosted server and attaches that bearer.
