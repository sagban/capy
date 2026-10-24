"""Gemini 3 keeps the model's own function-call message, including its thought signature."""

from google.genai import types

from agent.llm.vertex import append_model_turn


def test_tool_round_appends_the_original_model_message():
    part = types.Part.from_function_call(name="search_catalog", args={"query": "egg"})
    part.thought_signature = b"sig-bytes"
    model_content = types.Content(role="model", parts=[part])

    contents: list = []
    append_model_turn(
        contents,
        model_content,
        [{"name": "search_catalog", "result": {"hits": []}}],
        types,
    )

    assert contents[0] is model_content
    assert contents[0].parts[0].thought_signature == b"sig-bytes"
    assert contents[1].role == "tool"
    assert contents[1].parts[0].function_response.name == "search_catalog"
