"""One Gemini turn with typed tools."""

from __future__ import annotations

import os
from typing import Any

from agent.harness.mock_turn import pop_mock_turn


def generate(
    system: str,
    user: str,
    history: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]],
    tool_exchange: list[dict[str, Any]] | None = None,
    temperature: float,
) -> dict[str, Any]:
    if os.environ.get("CAPY_MOCK_AGENT") == "1":
        scripted = pop_mock_turn()
        if scripted:
            return scripted
        return {"kind": "text", "text": ""}
    from agent.llm.vertex import generate_with_tools

    return generate_with_tools(
        system=system,
        user_content=user,
        tool_declarations=tools,
        history=history,
        tool_exchange=tool_exchange,
        temperature=temperature,
    )
