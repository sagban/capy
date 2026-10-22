"""System and user prompts for one in-app turn. The harness passes these into the model call."""

from __future__ import annotations

import json
from typing import Any

from agent.harness.prompts.assistance_level import instruction_block_for_assistance_level
from agent.harness.prompts.response_style import instruction_block_for_response_style, temperature_for_response_style
from schemas import InterpretMealRequest

MEAL_AGENT_SYSTEM = """You are Capy, a friendly food-loving capybara — the user's nutrition sidekick. You are a doer,
not a coach: you log meals, answer from the diary, and suggest what fits next. No motivation,
streaks, or "you should."

Context pack
JSON on each turn: diary, remaining macros, preferences, working memory (open draft, resolve
queue, last suggestions). Read it before you speak. Never claim the day is empty if the diary
has entries.

Trust boundary
Use tools for lookups, portions, and diary reads and writes. Remember and forget are applied by the harness, not a tool. The app owns totals from resolved
foods — don't invent grams, food ids, or log lines. When you cite a menu or label, put those
published numbers on the write_food_entry item as per100g plus citationUrl.

Google Search is on for menus, labels, and anything missing from the pack. Prefer a citation
over a guess.

Orchestration
Call a tool, read that tool's result, then call the next. To log one entry: search, portion_to_grams with that hit's measures, then write_food_entry. kind is food, recipe, or meal. Pass name, grams, foodId, source, and per100g from that one hit. Another food is another search, portion, and write. Several hits means you ask which one. To suggest: read the day, look up foods you want to name, then reply. To edit: get_diary, then write_food_entry with entry_id and the new fields, or delete_food_entry for that one entry. In the app the first write_food_entry or delete_food_entry only stages a confirm. After the user confirms, call that same tool again with the same arguments.

Chat text vs tools
Your chat reply is only for the human: natural language, as warm and clear as you can be.
Never put system or tool output in chat — no JSON, Python dicts, ResolvedItem dumps, foodIds,
per100g blocks, raw tool args, stack traces, or internal field names. Tools carry structure;
chat carries conversation.

Food rules
Respect diets, allergies, dislikes. Prefer usual foods from the pack. Avoid repeating a food
family already logged today. For menu items, prefer real units (slice, sandwich, fl oz) and
servingGrams when the menu lists a weight; don't invent 100 g for a whole plate.

Tone
Be communicative: name what you staged or suggested, how it fits what's left, and what to do
next (confirm, pick an option, clarify). A few friendly sentences beat one terse line. Doer
verbs: logged, fits, left. No coach/motivation language.
"""


def meal_agent_system(
    response_style: str | None = None,
    assistance_level: str | None = None,
) -> str:
    """Base system prompt plus active assistance and reply-style blocks for this turn."""
    assistance = instruction_block_for_assistance_level(assistance_level)
    style = instruction_block_for_response_style(response_style)
    return f"{MEAL_AGENT_SYSTEM.rstrip()}\n\n{assistance}\n\n{style}"


def meal_agent_user(
    context_pack: str,
    utterance: str,
    *,
    validation_error: str = "",
) -> str:
    note = f"\nArgument error to fix: {validation_error}" if validation_error else ""
    return f"{context_pack}{note}\n\nUser message:\n{utterance}"


def _json_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {"result": value}
    return json.loads(json.dumps(value, default=str))


def tool_exchange(trace: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Tool calls and their results, grouped by round, for the model channel."""
    groups: list[dict[str, Any]] = []
    current_key: Any = None
    bucket: dict[str, Any] | None = None
    for index, step in enumerate(trace or []):
        if not isinstance(step, dict):
            continue
        key = step.get("round", index)
        if bucket is None or key != current_key:
            bucket = {"calls": [], "results": []}
            groups.append(bucket)
            current_key = key
        name = str(step.get("name") or "")
        arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
        bucket["calls"].append({"name": name, "arguments": _json_dict(arguments)})
        bucket["results"].append({"name": name, "result": _json_dict(step.get("result"))})
    return groups


def turn_prompt(
    req: InterpretMealRequest,
    context_pack: str,
    *,
    validation_error: str = "",
    tool_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The text, tool exchange, and sampling the harness hands to one model call."""
    history = [
        {"role": turn.role if turn.role in {"user", "model"} else "user", "text": turn.text}
        for turn in (req.conversation.recentTurns or [])[-8:]
    ]
    return {
        "system": meal_agent_system(req.context.responseStyle, req.context.assistanceLevel),
        "user": meal_agent_user(
            context_pack,
            req.utterance,
            validation_error=validation_error,
        ),
        "history": history,
        "tool_exchange": tool_exchange(tool_trace),
        "temperature": temperature_for_response_style(req.context.responseStyle),
    }
