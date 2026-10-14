"""Capy LangGraph ReAct harness entrypoint.

Production auth:
- Gemini via Vertex AI + ADC (GCP billing / credits on capy-dogfood)
- USDA key via Secret Manager → injected as USDA_FDC_API_KEY
"""

from __future__ import annotations

import logging

# Do not register Phoenix at import — OTEL setup has crashed the emulator worker.
# Spans call phoenix_tracing.setup() lazily on first use.
import phoenix_tracing

from firebase_admin import initialize_app
from firebase_functions import https_fn, options
from firebase_functions.params import SecretParam

from graph import run_interpret
from schemas import request_from_dict

logger = logging.getLogger("capy.interpret_meal")

initialize_app()

USDA_FDC_API_KEY = SecretParam("USDA_FDC_API_KEY")


@https_fn.on_call(
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=120,
    secrets=[USDA_FDC_API_KEY],
)
def interpret_meal(req: https_fn.CallableRequest) -> dict:
    """Authenticated callable — ReAct agent + tools + HITL."""
    if req.auth is None:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.UNAUTHENTICATED,
            message="Sign in required.",
        )
    raw = req.data if isinstance(req.data, dict) else {}
    utterance = str(raw.get("utterance") or "")[:80]
    logger.info("interpret_meal start utterance=%r", utterance)
    try:
        parsed = request_from_dict(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("interpret_meal invalid payload: %s", exc)
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
            message="Couldn’t read that request. Try again.",
        ) from exc

    try:
        with phoenix_tracing.chain_span(
            "interpret_meal",
            input_value=utterance,
        ) as root:
            response = run_interpret(parsed.model_dump(mode="json"))
            # Strip free-floating macro fields from candidates; keep provisionalPer100g for web.
            for candidate in response.get("candidates") or []:
                if not isinstance(candidate, dict):
                    continue
                source = (candidate.get("source") or "").lower()
                for key in ("calories", "proteinG", "carbsG", "fatG"):
                    candidate.pop(key, None)
                if source not in {"web", "diary"} and not source.startswith("web"):
                    candidate.pop("per100g", None)
            phoenix_tracing.set_output(
                root,
                {
                    "intent": response.get("intent"),
                    "assistantMessage": response.get("assistantMessage"),
                    "pendingAction": (response.get("pendingAction") or {}).get("type")
                    if isinstance(response.get("pendingAction"), dict)
                    else None,
                    "warnings": response.get("warnings"),
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("interpret_meal run failed: %s", exc)
        return {
            "intent": "unknown",
            "candidates": [],
            "assistantMessage": "",
            "warnings": ["agent_unavailable"],
            "memoryProposals": [],
            "pendingAction": None,
            "suggestionOptions": [],
        }

    logger.info(
        "interpret_meal done intent=%s msg_len=%s",
        response.get("intent"),
        len(response.get("assistantMessage") or ""),
    )
    return response
