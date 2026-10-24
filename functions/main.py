"""Cloud Function entry. Agent = LLM + harness (`agent/`).

Production auth:
- Gemini via Vertex AI + ADC on the Firebase project's GCP project
- USDA key via Secret Manager → injected as USDA_FDC_API_KEY
"""

from __future__ import annotations

# macOS + gunicorn: forked workers SIGSEGV when native code hits CFPreferences
# after fork (_scproxy / Arrow curl). Mitigations must run at import time.
import os
import sys

if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
    try:
        import urllib.request

        urllib.request.getproxies = urllib.request.getproxies_environment
    except Exception:  # noqa: BLE001
        pass
    # Load the app in the gunicorn master before fork so curl/Arrow init pre-fork.
    try:
        from functions_framework._http import gunicorn as _ff_gunicorn

        _ff_guni_init = _ff_gunicorn.GunicornApplication.__init__

        def _ff_guni_init_preload(self, app, host, port, debug, **options):  # type: ignore[no-untyped-def]
            options.setdefault("preload_app", True)
            return _ff_guni_init(self, app, host, port, debug, **options)

        _ff_gunicorn.GunicornApplication.__init__ = _ff_guni_init_preload  # type: ignore[method-assign]
    except Exception:  # noqa: BLE001
        pass

import logging

# Do not register Phoenix at import — OTEL setup has crashed the emulator worker.
# Spans call phoenix_tracing.setup() lazily on first use.
import phoenix_tracing

from firebase_admin import initialize_app
from firebase_functions import https_fn, options
from firebase_functions.params import SecretParam

from agent.auth import AuthError, exchange_firebase_for_access, resolve_callable_uid
from interpret_api import interpret_meal_for_uid
from user_api import (
    handle_delete_library_item,
    handle_delete_meal,
    handle_get_thread,
    handle_list_diary,
    handle_list_library,
    handle_log_meal,
    handle_lookup_barcode,
    handle_patch_profile,
    handle_patch_thread,
    handle_upsert_library_item,
)

logger = logging.getLogger("capy.interpret_meal")

initialize_app()

USDA_FDC_API_KEY = SecretParam("USDA_FDC_API_KEY")
API_ACCESS_TOKEN_SECRET = SecretParam("API_ACCESS_TOKEN_SECRET")


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=120,
    secrets=[USDA_FDC_API_KEY, API_ACCESS_TOKEN_SECRET],
)
def interpret_meal(req: https_fn.CallableRequest) -> dict:
    """Authenticated callable — ReAct agent + tools + HITL."""
    uid = resolve_callable_uid(req)
    raw = req.data if isinstance(req.data, dict) else {}
    try:
        return interpret_meal_for_uid(uid, raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("interpret_meal invalid payload: %s", exc)
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="Couldn’t read that request. Try again.",
        ) from exc


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def patch_profile(req: https_fn.CallableRequest) -> dict:
    """Merge profile fields on users/{uid} (meal plan, prefs, targets, timezone)."""
    return handle_patch_profile(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def log_meal(req: https_fn.CallableRequest) -> dict:
    """Write a confirmed meal to users/{uid}/days/{dayKey}/entries/{entryId}."""
    return handle_log_meal(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def delete_meal(req: https_fn.CallableRequest) -> dict:
    """Soft-delete a meal entry at users/{uid}/days/{dayKey}/entries/{entryId}."""
    return handle_delete_meal(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=30,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def get_thread(req: https_fn.CallableRequest) -> dict:
    """Read users/{uid}/threads/{threadId} for Capy chat history."""
    return handle_get_thread(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=30,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def patch_thread(req: https_fn.CallableRequest) -> dict:
    """Append assistant turns or day-rollover notes on the conversation thread."""
    return handle_patch_thread(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=30,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def exchange_access_token(req: https_fn.CallableRequest) -> dict:
    """Exchange a Firebase ID token for a short-lived Capy access token (MCP / HTTP clients)."""
    raw = req.data if isinstance(req.data, dict) else {}
    try:
        return exchange_firebase_for_access(raw)
    except AuthError as exc:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message=str(exc),
        ) from exc


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=30,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def lookup_barcode(req: https_fn.CallableRequest) -> dict:
    """Exact GTIN → Open Food Facts product for Manual Log barcode scanner."""
    return handle_lookup_barcode(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def upsert_library_item(req: https_fn.CallableRequest) -> dict:
    """Create or replace users/{uid}/library/{id}."""
    return handle_upsert_library_item(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def delete_library_item(req: https_fn.CallableRequest) -> dict:
    """Soft-delete users/{uid}/library/{id}."""
    return handle_delete_library_item(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def list_library(req: https_fn.CallableRequest) -> dict:
    """List users/{uid}/library for client restore / merge."""
    return handle_list_library(req)


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_256,
    timeout_sec=60,
    secrets=[API_ACCESS_TOKEN_SECRET],
)
def list_diary(req: https_fn.CallableRequest) -> dict:
    """List users/{uid}/days/*/entries so the iPhone can restore the diary."""
    return handle_list_diary(req)


# Warm Phoenix/Arrow (curl) during gunicorn preload on macOS so fork children
# do not call Curl_macos_init for the first time post-fork.
if sys.platform == "darwin":
    phoenix_tracing.setup()
