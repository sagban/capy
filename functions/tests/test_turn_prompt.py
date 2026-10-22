"""The user message stays conversation. Tool results travel on the tool channel."""

from agent.harness.prompts.prompt import tool_exchange, turn_prompt
from schemas import request_from_dict


def test_user_message_omits_tool_results():
    req = request_from_dict({"utterance": "log an egg", "dayKey": "2026-10-13"})
    trace = [
        {
            "name": "search_catalog",
            "arguments": {"query": "egg"},
            "result": {"hits": [{"displayName": "Egg"}]},
            "round": 1,
        }
    ]
    packed = turn_prompt(req, "{}", tool_trace=trace)
    assert "Tool results" not in packed["user"]
    assert "displayName" not in packed["user"]
    assert "log an egg" in packed["user"]
    assert packed["tool_exchange"][0]["results"][0]["result"]["hits"][0]["displayName"] == "Egg"


def test_tool_exchange_groups_one_round():
    trace = [
        {"name": "search_catalog", "arguments": {"query": "egg"}, "result": {"hits": []}, "round": 1},
        {"name": "search_usda", "arguments": {"query": "egg"}, "result": {"hits": []}, "round": 1},
        {"name": "portion_to_grams", "arguments": {"quantity": 1}, "result": {"grams": 50}, "round": 2},
    ]
    groups = tool_exchange(trace)
    assert len(groups) == 2
    assert [call["name"] for call in groups[0]["calls"]] == ["search_catalog", "search_usda"]
    assert groups[1]["results"][0]["result"] == {"grams": 50}
