"""Assistance dial → per-turn system prompt injection."""

from agent.harness.prompts.assistance_level import (
    DEFAULT_ASSISTANCE_LEVEL,
    instruction_block_for_assistance_level,
    normalize_assistance_level,
)
from agent.harness.prompts import MEAL_AGENT_SYSTEM, meal_agent_system
from agent.harness.prompts.response_style import instruction_block_for_response_style


def test_normalize_assistance_level_defaults_to_full_assist():
    assert DEFAULT_ASSISTANCE_LEVEL == "fullAssist"
    assert normalize_assistance_level(None) == "fullAssist"
    assert normalize_assistance_level("") == "fullAssist"
    assert normalize_assistance_level("unknown") == "fullAssist"
    assert normalize_assistance_level("guided") == "guided"
    assert normalize_assistance_level("quiet") == "quiet"


def test_instruction_block_injects_single_level_only():
    full = instruction_block_for_assistance_level("fullAssist")
    guided = instruction_block_for_assistance_level("guided")
    quiet = instruction_block_for_assistance_level("quiet")

    assert "offer the next meal" in full
    assert "offer the next meal" not in guided
    assert "offer the next meal" not in quiet

    assert "clearly invites it" in guided
    assert "clearly invites it" not in full

    assert "do not suggest unless they asked" in quiet
    assert "do not suggest unless they asked" not in full

    assert instruction_block_for_assistance_level(None) == full
    assert "Never change the assistance level yourself." in full


def test_meal_agent_system_appends_active_assistance_block():
    system = meal_agent_system("precise", "guided")
    assert system.startswith(MEAL_AGENT_SYSTEM.rstrip())
    assert "clearly invites it" in system
    assert "offer the next meal" not in system
    assert system.endswith(instruction_block_for_response_style("precise"))

    assert "fullAssist:" not in system
    assert "guided:" not in system
    assert "quiet:" not in system


def test_base_prompt_has_no_static_assistance_modes():
    assert "fullAssist:" not in MEAL_AGENT_SYSTEM
    assert "guided:" not in MEAL_AGENT_SYSTEM
    assert "quiet:" not in MEAL_AGENT_SYSTEM
