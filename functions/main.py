"""Capy LangGraph harness entrypoint (Phase 1 implementation).

Phase 0: scaffold only — no Gemini/USDA calls yet.
"""

from firebase_functions import https_fn
from firebase_admin import initialize_app

initialize_app()


@https_fn.on_call()
def interpret_meal(req: https_fn.CallableRequest) -> dict:
    """Authenticated callable. Full LangGraph wiring is Phase 1."""
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="Sign in required.",
        )
    return {
        "intent": "unknown",
        "candidates": [],
        "clarifyingQuestion": None,
        "assistantMessage": "harness scaffold — not implemented yet",
        "warnings": ["phase0_scaffold"],
    }
