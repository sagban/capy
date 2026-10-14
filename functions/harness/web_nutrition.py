"""One grounded lookup for a per-100g density. Accepted only with a citation and Atwater."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional

from harness.checks import density_ok
from schemas import MacroTotals

logger = logging.getLogger("capy.web_nutrition")

Generate = Callable[[str], Optional[dict[str, Any]]]


def _parse_density(payload: dict[str, Any]) -> Optional[tuple[MacroTotals, str]]:
    url = str(payload.get("citationUrl") or payload.get("citation") or "").strip()
    if not url.startswith("http"):
        return None
    try:
        macros = MacroTotals(
            calories=float(payload["calories"]),
            proteinG=float(payload.get("proteinG") or 0),
            carbsG=float(payload.get("carbsG") or 0),
            fatG=float(payload.get("fatG") or 0),
        )
    except (KeyError, TypeError, ValueError):
        return None
    if not density_ok(macros.calories, macros.proteinG, macros.carbsG, macros.fatG):
        return None
    return macros, url


def _grounded_generate(query: str) -> Optional[dict[str, Any]]:
    try:
        from google.genai import types

        from vertex_gemini import _model, get_vertex_client
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_nutrition_import_failed: %s", exc)
        return None
    prompt = (
        "Look up nutrition for this food. Reply with JSON only: "
        '{"calories": number, "proteinG": number, "carbsG": number, "fatG": number, '
        '"citationUrl": "https://..."}. Numbers are per 100 grams. '
        "citationUrl must be a page that states those numbers. "
        f"Food: {query}"
    )
    try:
        client = get_vertex_client()
        result = client.models.generate_content(
            model=_model(),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        text = (result.text or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_nutrition_failed: %s", exc)
        return None
    return _json_object(text)


def _json_object(text: str) -> Optional[dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except Exception:  # noqa: BLE001
            return None


def lookup_web_nutrition(query: str, generate: Generate | None = None) -> Optional[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return None
    payload = (generate or _grounded_generate)(q)
    if not isinstance(payload, dict):
        return None
    parsed = _parse_density(payload)
    if parsed is None:
        return None
    macros, url = parsed
    return {"per100g": macros, "citationUrl": url}
