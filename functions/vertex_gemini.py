"""Gemini via Vertex AI (ADC). Bills GCP project credits — no AI Studio API key."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Optional

from schemas import InterpretMealRequest, MealIntent

logger = logging.getLogger("capy.vertex")

DEFAULT_PROJECT = "capy-dogfood"
DEFAULT_LOCATION = "us-central1"
DEFAULT_MODEL = "gemini-2.0-flash-001"


def _project_id() -> str:
    return (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
        or DEFAULT_PROJECT
    )


def _location() -> str:
    return os.environ.get("GOOGLE_CLOUD_LOCATION") or DEFAULT_LOCATION


def _model() -> str:
    return os.environ.get("VERTEX_GEMINI_MODEL") or DEFAULT_MODEL


@lru_cache(maxsize=1)
def get_vertex_client():
    from google import genai

    return genai.Client(
        vertexai=True,
        project=_project_id(),
        location=_location(),
    )


def classify_intent(req: InterpretMealRequest) -> Optional[MealIntent]:
    """Structured intent classification. Returns None on failure (caller uses heuristics)."""
    try:
        client = get_vertex_client()
    except Exception as exc:  # noqa: BLE001
        logger.warning("vertex_client_unavailable: %s", exc)
        return None

    prompt = {
        "utterance": req.utterance,
        "summary": req.conversation.summary,
        "recentTurns": [t.model_dump() for t in req.conversation.recentTurns[-6:]],
        "workingMemory": (
            req.conversation.workingMemory.model_dump()
            if req.conversation.workingMemory
            else None
        ),
        "longTermMemory": [n.model_dump() for n in req.longTermMemory[:20]],
        "diets": req.preferenceContext.diets,
        "intents": [i.value for i in MealIntent],
        "rules": [
            "Return JSON only: {\"intent\": \"<one of intents>\"}",
            "Never invent calorie or macro numbers.",
            "Use clarify when portion is ambiguous.",
            "Use update_memory for remember/forget standing facts.",
            "Use suggest_meal for suggestion requests.",
            "Use log_meal when user reports food eaten.",
        ],
    }

    try:
        result = client.models.generate_content(
            model=_model(),
            contents=json.dumps(prompt),
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        )
        data = _parse_json(result.text or "")
        intent_raw = str(data.get("intent", "unknown"))
        return MealIntent(intent_raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("vertex_intent_failed: %s", exc)
        return None


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text or "{}")
