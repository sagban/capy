"""Response style dial → Gemini temperature."""

from agent.context_loader import _interpret_context_from_raw
from agent.harness.memory.semantic import semantic_block
from agent.llm.prompt import MEAL_AGENT_SYSTEM, meal_agent_system
from agent.llm.response_style import (
    DEFAULT_RESPONSE_STYLE,
    instruction_block_for_response_style,
    temperature_for_response_style,
)
from schemas import InterpretContext, InterpretMealRequest, request_from_dict


def test_temperature_mapping_defaults_to_balanced():
    assert DEFAULT_RESPONSE_STYLE == "balanced"
    assert temperature_for_response_style(None) == 0.5
    assert temperature_for_response_style("") == 0.5
    assert temperature_for_response_style("precise") == 0.2
    assert temperature_for_response_style("balanced") == 0.5
    assert temperature_for_response_style("creative") == 0.8
    assert temperature_for_response_style("unknown") == 0.5


def test_interpret_context_from_profile_and_request():
    profile = {"assistanceLevel": "guided", "responseStyle": "creative"}
    ctx = _interpret_context_from_raw({"context": {"responseStyle": "balanced"}}, profile)
    assert ctx.assistanceLevel == "guided"
    assert ctx.responseStyle == "balanced"

    ctx2 = _interpret_context_from_raw({}, profile)
    assert ctx2.responseStyle == "creative"


def test_request_from_dict_carries_response_style():
    raw = {
        "utterance": "eggs",
        "timezone": "UTC",
        "dayKey": "2026-10-16",
        "diaryContext": {
            "remaining": {"calories": 2000, "proteinG": 140, "carbsG": 200, "fatG": 65},
            "today": [],
            "previousDays": [],
        },
        "context": {"assistanceLevel": "fullAssist", "responseStyle": "balanced"},
    }
    req = request_from_dict(raw)
    assert req.context.responseStyle == "balanced"
    assert semantic_block(req)["responseStyle"] == "balanced"


def test_interpret_context_default():
    assert InterpretContext().responseStyle == "balanced"


def test_instruction_block_injects_single_style_only():
    precise = instruction_block_for_response_style("precise")
    balanced = instruction_block_for_response_style("balanced")
    creative = instruction_block_for_response_style("creative")

    assert "shortest correct answer" in precise
    assert "shortest correct answer" not in balanced
    assert "shortest correct answer" not in creative

    assert "short helpful aside" in balanced
    assert "short helpful aside" not in precise

    assert "warmer, more varied phrasing" in creative
    assert "warmer, more varied phrasing" not in precise

    assert instruction_block_for_response_style(None) == balanced
    assert "temperature" not in precise.lower()


def test_meal_agent_system_appends_active_style_block():
    system = meal_agent_system("balanced", "quiet")
    assert system.startswith(MEAL_AGENT_SYSTEM.rstrip())
    assert system.endswith(instruction_block_for_response_style("balanced"))
    assert "short helpful aside" in system
    assert "warmer, more varied phrasing" not in system
    assert "do not suggest unless they asked" in system
