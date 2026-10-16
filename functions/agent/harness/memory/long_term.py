"""Durable notes the client stores. The model may propose add/remove."""

from __future__ import annotations

from typing import Any

from schemas import InterpretMealRequest


def long_term_block(req: InterpretMealRequest) -> dict[str, Any]:
    return {
        "notes": [n.model_dump() for n in req.longTermMemory],
    }
