"""Bearer auth: Firebase ID tokens (iOS / web) and Capy short-lived access tokens (MCP, Alexa)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import jwt
from firebase_admin import auth as firebase_auth
from firebase_functions import https_fn

logger = logging.getLogger("capy.auth")

ACCESS_TOKEN_TTL_SECONDS = 3600
CAPPY_ISSUER = "capy"
CAPPY_AUDIENCE = "capy-api"


class AuthError(Exception):
    pass


def _signing_secret() -> str:
    secret = (os.environ.get("API_ACCESS_TOKEN_SECRET") or "").strip()
    if not secret:
        raise AuthError("API access tokens are not configured.")
    return secret


def verify_firebase_id_token(id_token: str) -> str:
    token = (id_token or "").strip()
    if not token:
        raise AuthError("Missing ID token.")
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as exc:  # noqa: BLE001
        raise AuthError("Invalid Firebase ID token.") from exc
    uid = str(decoded.get("uid") or "").strip()
    if not uid:
        raise AuthError("Invalid Firebase ID token.")
    return uid


def mint_access_token(uid: str) -> str:
    user_id = (uid or "").strip()
    if not user_id:
        raise AuthError("uid required.")
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iss": CAPPY_ISSUER,
        "aud": CAPPY_AUDIENCE,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, _signing_secret(), algorithm="HS256")


def verify_access_token(token: str) -> str:
    raw = (token or "").strip()
    if not raw:
        raise AuthError("Missing access token.")
    try:
        decoded = jwt.decode(
            raw,
            _signing_secret(),
            algorithms=["HS256"],
            audience=CAPPY_AUDIENCE,
            issuer=CAPPY_ISSUER,
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthError("Invalid or expired access token.") from exc
    uid = str(decoded.get("sub") or "").strip()
    if not uid:
        raise AuthError("Invalid access token.")
    return uid


def resolve_bearer_to_uid(bearer: str) -> str:
    """Accept Firebase ID token or Capy access JWT."""
    token = (bearer or "").strip()
    if not token:
        raise AuthError("Missing bearer token.")
    try:
        return verify_firebase_id_token(token)
    except AuthError:
        return verify_access_token(token)


def bearer_from_callable(req: https_fn.CallableRequest) -> str | None:
    raw = getattr(req, "raw_request", None)
    if raw is None:
        return None
    headers = getattr(raw, "headers", None)
    if headers is None:
        return None
    header = headers.get("Authorization") or headers.get("authorization") or ""
    if not isinstance(header, str):
        return None
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def resolve_callable_uid(req: https_fn.CallableRequest) -> str:
    """Firebase callable auth (SDK) or Authorization: Bearer on the HTTP callable wire."""
    if req.auth is not None:
        return req.auth.uid
    token = bearer_from_callable(req)
    if not token:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="Sign in required.",
        )
    try:
        return resolve_bearer_to_uid(token)
    except AuthError as exc:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message=str(exc),
        ) from exc


def exchange_firebase_for_access(raw: dict[str, Any]) -> dict[str, Any]:
    id_token = str(
        raw.get("firebaseIdToken") or raw.get("idToken") or raw.get("firebase_id_token") or ""
    ).strip()
    if not id_token:
        raise AuthError("firebaseIdToken is required.")
    uid = verify_firebase_id_token(id_token)
    access = mint_access_token(uid)
    return {
        "accessToken": access,
        "tokenType": "Bearer",
        "expiresIn": ACCESS_TOKEN_TTL_SECONDS,
        "uid": uid,
    }
