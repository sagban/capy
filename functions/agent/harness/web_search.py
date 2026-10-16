"""Internet search via Vertex Gemini Google Search grounding."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("capy.web_search")


def web_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Return grounded web snippets. Never raises — empty results on failure."""
    q = (query or "").strip()
    if not q:
        return {"results": [], "error": "empty_query"}

    try:
        from google.genai import types

        from agent.llm.vertex import get_vertex_client, _model
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_search_import_failed: %s", exc)
        return {"results": [], "error": "unavailable"}

    try:
        client = get_vertex_client()
        # Grounding with Google Search (Vertex).
        config = types.GenerateContentConfig(
            temperature=0.2,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
        prompt = (
            "Search the public web for food nutrition or menu information. "
            "Return a short factual summary of what you find for this query. "
            "Include calorie/protein/carb/fat numbers only if explicitly stated in sources. "
            f"Query: {q}"
        )
        result = client.models.generate_content(
            model=_model(),
            contents=prompt,
            config=config,
        )
        text = (result.text or "").strip()
        citations: list[dict[str, str]] = []
        # Best-effort grounding metadata extraction across SDK shapes.
        try:
            candidates = getattr(result, "candidates", None) or []
            if candidates:
                meta = getattr(candidates[0], "grounding_metadata", None)
                chunks = getattr(meta, "grounding_chunks", None) or []
                for chunk in chunks[:limit]:
                    web = getattr(chunk, "web", None)
                    if web is None and isinstance(chunk, dict):
                        web = chunk.get("web")
                    if web is None:
                        continue
                    title = getattr(web, "title", None) or (web.get("title") if isinstance(web, dict) else None)
                    uri = getattr(web, "uri", None) or (web.get("uri") if isinstance(web, dict) else None)
                    if title or uri:
                        citations.append(
                            {
                                "title": (title or "source")[:200],
                                "uri": (uri or "")[:500],
                            }
                        )
        except Exception:  # noqa: BLE001
            pass

        return {
            "results": [
                {
                    "summary": text[:2000],
                    "citations": citations[:limit],
                }
            ],
            "query": q,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("web_search_failed: %s", exc)
        return {"results": [], "error": "unavailable"}
