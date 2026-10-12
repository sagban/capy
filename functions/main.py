"""Capy LangGraph harness entrypoint (Phase 1).

Production auth:
- Gemini via Vertex AI + ADC (GCP billing / credits on capy-dogfood)
- USDA key via Secret Manager → injected as USDA_FDC_API_KEY
"""

from __future__ import annotations

from firebase_admin import initialize_app
from firebase_functions import https_fn, options
from firebase_functions.params import SecretParam

from graph import run_interpret
from schemas import request_from_dict

initialize_app()

USDA_FDC_API_KEY = SecretParam("USDA_FDC_API_KEY")


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=60,
    secrets=[USDA_FDC_API_KEY],
)
def interpret_meal(req: https_fn.CallableRequest) -> dict:
    """Authenticated callable — LangGraph meal intent + tools."""
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="Sign in required.",
        )
    raw = req.data if isinstance(req.data, dict) else {}
    try:
        parsed = request_from_dict(raw)
    except Exception as exc:  # noqa: BLE001
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message=f"Invalid request: {exc}",
        ) from exc

    # Fail closed: never return trusted macros from the model path.
    response = run_interpret(parsed.model_dump(mode="json"))
    for candidate in response.get("candidates") or []:
        for key in ("calories", "proteinG", "carbsG", "fatG", "per100g"):
            candidate.pop(key, None)
    return response
