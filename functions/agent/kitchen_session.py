"""Sign-in page that returns a Capy access token for MCP clients.

The user signs in with the same email and password as the iPhone app. The
response is the bearer token and a ready MCP config. Nothing is stored.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from agent.auth import AuthError, exchange_firebase_for_access

_SIGN_IN_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"


def _web_api_key() -> str:
    import os

    key = (os.environ.get("FIREBASE_WEB_API_KEY") or "").strip()
    if not key:
        raise AuthError("Sign-in is not configured.")
    return key


def _firebase_error_message(payload: dict[str, Any]) -> str:
    message = str((payload.get("error") or {}).get("message") or "")
    if message.startswith(("INVALID_PASSWORD", "EMAIL_NOT_FOUND", "INVALID_LOGIN_CREDENTIALS")):
        return "Email or password is wrong."
    if message.startswith("USER_DISABLED"):
        return "This account is disabled."
    return "Sign-in failed."


def sign_in_id_token(email: str, password: str) -> str:
    """Return a Firebase ID token. Raises AuthError on bad credentials."""
    response = httpx.post(
        _SIGN_IN_URL,
        params={"key": _web_api_key()},
        json={"email": email.strip(), "password": password, "returnSecureToken": True},
        timeout=20.0,
    )
    payload = response.json() if response.content else {}
    if response.status_code != 200:
        raise AuthError(_firebase_error_message(payload if isinstance(payload, dict) else {}))
    id_token = str(payload.get("idToken") or "").strip()
    if not id_token:
        raise AuthError("Sign-in failed.")
    return id_token


def _mcp_url(request: Request) -> str:
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc).split(",")[0].strip()
    return f"{proto}://{host}/mcp/"


def register_kitchen(app: FastAPI) -> None:
    @app.get("/kitchen")
    async def kitchen_page() -> HTMLResponse:
        return HTMLResponse(_PAGE)

    @app.post("/kitchen/session")
    async def kitchen_session(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Email and password are required.") from exc
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Email and password are required.")
        email = str(body.get("email") or "")
        password = str(body.get("password") or "")
        if not email.strip() or not password:
            raise HTTPException(status_code=400, detail="Email and password are required.")
        try:
            id_token = sign_in_id_token(email, password)
            minted = exchange_firebase_for_access({"firebaseIdToken": id_token})
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return JSONResponse(
            {
                "accessToken": minted["accessToken"],
                "tokenType": minted["tokenType"],
                "expiresIn": minted["expiresIn"],
                "mcpUrl": _mcp_url(request),
            }
        )


_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Capy MCP token</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #F3EFE7;
      --surface: #FFFCF7;
      --text: #1F1B16;
      --muted: #6B645A;
      --accent: #1FA971;
      --soft: #C6F0DC;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; background: var(--bg); color: var(--text);
      font: 17px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main { max-width: 40rem; margin: 0 auto; padding: 2.5rem 1.25rem 3rem; }
    h1 { font-size: 1.75rem; font-weight: 650; margin: 0 0 0.35rem; }
    p.lead { color: var(--muted); margin: 0 0 1.5rem; }
    form, .card { background: var(--surface); border-radius: 16px; padding: 1rem; }
    label { display: block; font-size: 0.85rem; color: var(--muted); margin: 0.75rem 0 0.3rem; }
    input, textarea {
      width: 100%; border: 0; background: var(--bg); color: var(--text);
      border-radius: 12px; padding: 0.75rem 0.85rem; font: inherit;
    }
    textarea { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem; }
    button {
      margin-top: 0.9rem; margin-right: 0.4rem; border: 0; background: var(--accent); color: white;
      border-radius: 999px; padding: 0.7rem 1.1rem; font: inherit; font-weight: 600;
    }
    button.quiet { background: transparent; color: var(--muted); }
    .err { color: #E67E22; margin-top: 0.75rem; }
    .note { color: var(--muted); font-size: 0.9rem; margin: 0.75rem 0 0; }
    [hidden] { display: none !important; }
  </style>
</head>
<body>
  <main>
    <h1>MCP token</h1>
    <p class="lead">Sign in with your Capy account. Copy the token into your MCP client. It lasts 1 hour.</p>
    <form id="sign-in">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" autocomplete="username" required />
      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required />
      <button type="submit">Sign in</button>
      <p class="err" id="sign-in-err" hidden></p>
    </form>
    <section id="token" class="card" hidden>
      <label for="access-token">Token</label>
      <textarea id="access-token" rows="5" readonly></textarea>
      <label for="config">MCP config</label>
      <textarea id="config" rows="14" readonly></textarea>
      <button type="button" id="copy-token">Copy token</button>
      <button type="button" id="copy-config">Copy config</button>
      <button class="quiet" type="button" id="again">Sign in again</button>
      <p class="note" id="note"></p>
    </section>
  </main>
  <script>
    const signIn = document.querySelector("#sign-in");
    const tokenCard = document.querySelector("#token");
    const signInErr = document.querySelector("#sign-in-err");
    const accessToken = document.querySelector("#access-token");
    const configBox = document.querySelector("#config");
    const note = document.querySelector("#note");

    function showErr(message) {
      signInErr.hidden = !message;
      signInErr.textContent = message || "";
    }

    function configFor(url, token) {
      return JSON.stringify({
        mcpServers: {
          cappy: {
            url,
            headers: { Authorization: "Bearer " + token }
          }
        }
      }, null, 2);
    }

    async function copyText(value, label) {
      await navigator.clipboard.writeText(value);
      note.textContent = label;
    }

    signIn.addEventListener("submit", async (event) => {
      event.preventDefault();
      showErr("");
      const res = await fetch("/kitchen/session", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: signIn.email.value, password: signIn.password.value }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showErr(data.detail || "Sign-in failed.");
        return;
      }
      signIn.password.value = "";
      accessToken.value = data.accessToken || "";
      configBox.value = configFor(data.mcpUrl, data.accessToken || "");
      const hours = Math.round((data.expiresIn || 3600) / 3600);
      note.textContent = "Lasts " + hours + " hour. Paste the token or the config into your MCP client.";
      signIn.hidden = true;
      tokenCard.hidden = false;
    });

    document.querySelector("#copy-token").addEventListener("click", () => {
      copyText(accessToken.value, "Token copied.");
    });
    document.querySelector("#copy-config").addEventListener("click", () => {
      copyText(configBox.value, "Config copied.");
    });
    document.querySelector("#again").addEventListener("click", () => {
      tokenCard.hidden = true;
      signIn.hidden = false;
      accessToken.value = "";
      configBox.value = "";
    });
  </script>
</body>
</html>
"""
