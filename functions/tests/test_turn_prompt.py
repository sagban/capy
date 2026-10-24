"""The user message stays conversation. Tool results go back on the same Gemini conversation."""

from agent.harness.prompts.prompt import turn_prompt
from schemas import request_from_dict


def test_user_message_is_the_utterance():
    req = request_from_dict({"utterance": "log an egg", "dayKey": "2026-10-13"})
    packed = turn_prompt(req, "{}")
    assert "Tool results" not in packed["user"]
    assert "displayName" not in packed["user"]
    assert "log an egg" in packed["user"]
    assert "tool_exchange" not in packed
