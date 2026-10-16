"""One Gemini turn with typed tools."""

from __future__ import annotations

import os
from typing import Any

from agent.harness.mock_turn import pop_mock_turn
from agent.harness.tools.registry import TOOL_DECLARATIONS, validate_calls
from agent.llm.prompt import MEAL_AGENT_SYSTEM, meal_agent_user
from schemas import InterpretMealRequest


def generate(system: str, user: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    if os.environ.get("CAPY_MOCK_AGENT") == "1":
        scripted = pop_mock_turn()
        if scripted:
            return scripted
        return {"kind": "text", "text": ""}
    from agent.llm.vertex import generate_with_tools

    return generate_with_tools(
        system=system,
        user_content=user,
        tool_declarations=TOOL_DECLARATIONS,
        history=history,
    )


def model_turn(
    req: InterpretMealRequest,
    context_pack: str,
    *,
    validation_error: str = "",
) -> dict[str, Any]:
    history = [
        {"role": turn.role if turn.role in {"user", "model"} else "user", "text": turn.text}
        for turn in (req.conversation.recentTurns or [])[-8:]
    ]
    user = meal_agent_user(context_pack, req.utterance, validation_error=validation_error)
    result = generate(MEAL_AGENT_SYSTEM, user, history)
    kind = result.get("kind")
    if kind == "error":
        return {"kind": "error", "message": result.get("message") or "unavailable"}
    if kind == "tool_calls":
        calls = list(result.get("calls") or [])
        text = str(result.get("text") or "")
        err = validate_calls(calls)
        if err:
            return {"kind": "bad_args", "message": err, "text": text}
        return {"kind": "tool_calls", "calls": calls, "text": text}
    text = str(result.get("text") or "")
    return {"kind": "text", "text": text}
