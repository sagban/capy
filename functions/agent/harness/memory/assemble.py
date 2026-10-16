"""One JSON context pack for the meal LLM."""

from __future__ import annotations

import json

from agent.harness.memory.episodic import episodic_block
from agent.harness.memory.long_term import long_term_block
from agent.harness.memory.semantic import semantic_block
from schemas import InterpretMealRequest


def build_pack(req: InterpretMealRequest) -> str:
    pack = {
        "utterance": req.utterance,
        "episodic": episodic_block(req),
        "semantic": semantic_block(req),
        "longTerm": long_term_block(req),
    }
    return json.dumps(pack, ensure_ascii=False)
