"""One Gemini text call. No tools."""

from __future__ import annotations

import os
from typing import Any

from agent.harness.mock_turn import pop_mock_turn
from agent.llm.prompt import MEAL_AGENT_SYSTEM, meal_agent_user
from schemas import InterpretMealRequest


def generate(system: str, user: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    if os.environ.get("CAPY_MOCK_AGENT") == "1":
        scripted = pop_mock_turn()
        if scripted:
            return scripted
        return {"kind": "text", "text": ""}
    from agent.llm.vertex import generate_chat

    return generate_chat(system=system, user_content=user, history=history)


def model_turn(req: InterpretMealRequest, context_pack: str) -> dict[str, Any]:
    history = [
        {"role": turn.role if turn.role in {"user", "model"} else "user", "text": turn.text}
        for turn in (req.conversation.recentTurns or [])[-8:]
    ]
    user = meal_agent_user(context_pack, req.utterance)
    result = generate(MEAL_AGENT_SYSTEM, user, history)
    kind = result.get("kind")
    if kind == "error":
        return {"kind": "error", "message": result.get("message") or "unavailable"}
    text = str(result.get("text") or "")
    return {"kind": "text", "text": text}
