"""One Gemini conversation. Tests pop scripted replies instead of calling Vertex."""

from __future__ import annotations

import os
from typing import Any

from agent.harness.mock_turn import pop_mock_turn


class MockConversation:
    """Scripted replies. Tool outputs are ignored because the next script does not read them."""

    def complete(self) -> dict[str, Any]:
        scripted = pop_mock_turn()
        if scripted:
            return scripted
        return {"kind": "text", "text": ""}

    def add_tool_results(self, results: list[dict[str, Any]]) -> None:
        del results

    def add_argument_error(self, message: str) -> None:
        del message


def open_conversation(
    system: str,
    user: str,
    history: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]],
    temperature: float,
) -> Any:
    if os.environ.get("CAPY_MOCK_AGENT") == "1":
        return MockConversation()
    from agent.llm.vertex import ToolConversation

    return ToolConversation(
        system=system,
        user_content=user,
        tool_declarations=tools,
        history=history,
        temperature=temperature,
    )
