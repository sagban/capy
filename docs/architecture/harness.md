# LangGraph harness architecture

Hosted on **Python Firebase Functions (2nd gen)**. Meal chat is one Vertex Gemini turn with typed tools, then deterministic execution. USDA key lives in Secret Manager (`USDA_FDC_API_KEY`). There is no skill router, no chip/action dispatch, and no phrase list.

**Agent = LLM + harness.** The user types every follow-up. Suggestions are display-only until they ask to log in chat (`new_entry` with `optionId`). Manual Log in the iOS Food Log tab is the non-AI escape hatch. The meal model has Google Search grounding on its Vertex turn; harness tools do not call the web.

The system prompt lives in [`functions/agent/llm/prompt.py`](../../functions/agent/llm/prompt.py). Tool descriptions live on the `@tool` functions in [`functions/agent/harness/tools/registry.py`](../../functions/agent/harness/tools/registry.py). Offline unit tests use `CAPY_MOCK_AGENT=1`.

`functions/` keeps the Cloud Function entry (`main.py`), the callable DTOs (`schemas.py`), and tracing. The agent is `functions/agent/`: **LLM** (`llm/`) + **harness** (`harness/`, including tools).

## Graph

```text
START -> prepare -> llm
llm --tool calls--> environment -> format -> respond -> END
llm --text only---> format -> respond -> END
llm --infra x2---> respond
```

| Node | File | Job |
|------|------|-----|
| prepare | `agent/turn.py` | Validate the request. Build the memory pack. Clear `calls`, `model_text`, `outcome`, and `response` so a checkpoint cannot leak the last turn. |
| llm | `agent/llm/model.py` | One Gemini call with meal tools plus Google Search grounding. Bad-args retry is inside this step (max 2). |
| environment | `agent/harness/tools/` | LangChain `@tool` registry. Pydantic `args_schema` plus `InjectedToolArg` for request context; Gemini declarations and argument checks are derived from the tools. |
| format | `agent/harness/format.py` | Uses the model's reply when present; appends a factual line from tool outcomes (suggestions, clarify, memory) when that adds numbers the user needs. No second model call. |
| respond | `agent/turn.py` | `normalize_outcome()`. Infra failure is `warnings: ["agent_unavailable"]` and an empty message. |

LangGraph compiles with a checkpointer. `thread_id` is `{firebase_uid}:{conversation.threadId}` (default thread `default`). Tests use `MemorySaver`. Production uses Firestore collection `agentGraphCheckpoints` (client reads/writes denied). Checkpoints store orchestration history; diary and remaining macros still arrive fresh on each request.

## Memory pack

`agent/harness/memory/assemble.py` builds one JSON context pack:

| Layer | Contents |
|-------|----------|
| Episodic | `threadId`, last 8 turns, compact older turns, summary, open resolve queue / draft, last suggestion ids |
| Semantic | remaining macros, slot budgets, usual foods, today + 14-day diary, diets / allergies / likes / dislikes |
| Long-term | `longTermMemory` notes |

Numbers in the pack are computed in Python (`meal_budget.py`), not by the meal model.

## Resolve

`agent/harness/resolve.py`, portions in `agent/harness/portions.py`.

1. Queries: food query, brand + query, model aliases, singular. At most 5. No miss cache.
2. `food_search.search_foods`. USDA search also asks for Survey (FNDDS). `high` commits. `medium` with 2 or more hits pauses with names in working memory. Otherwise the next query.
3. No automatic web resolve in harness; misses become `clarify_food` (Manual Log). Web context is for the model's grounded reply, not silent resolve.
4. Portion: explicit grams, or g/ml/oz/tsp/tbsp/cup at the `Units.swift` factors, or the food's own USDA/branded measures. Otherwise the reply asks how much, in text.
5. The first item that still needs the user pauses the turn. `resolveQueue` holds resolved items, the pending draft, remaining drafts, and candidate labels for the model. The next **utterance** continues it. The whole turn stops at 45 seconds.

Clarify options are **not** sent as UI chips. They stay in `workingMemory.resolveQueue` so the model can read them.

## Suggestions

`agent/harness/meal_budget.py`. A suggestion is a normal meal for that slot, not the day's remainder.

- Stated budget if the model passes one.
- Else the median kcal and protein of that slot when 3 or more days exist in the diary.
- Else plan-position weighted defaults on current remaining (last slot in `mealPlan` uses full remaining; earlier slots lighter). Slots come from `diaryContext.mealPlan` (client) or inferred diary `mealSlot` names — not a fixed breakfast/lunch/dinner list. Out-of-plan / snack-like slots use a small macro cap.
- Guide budgets may be scaled by `appetite` on `compose_suggestions` (`light` | `normal` | `hearty`; LLM interprets intent). Explicit `budget` overrides the guide. Only remaining macros are a hard ceiling.
- Always capped at remaining kcal. Remaining at or below 0 makes the budget 0 and every option `over`.

After resolve: if search is ambiguous, keep the top hit (suggestions are not HITL). Drop an option that hits a diet (vegetarian/vegan/pescatarian from prefs, notes, or this chat), an allergy, a dislike, or a food family already logged today. Cap each item at a household serving (oils/fats ~2 tbsp; staples 3 cups/servings or 500 g). An option that is only oil/butter is dropped. `within` means kcal at or under the slot budget. There is no calorie floor. `over` is shown. Suggestions are chat, not cards. Logging one is a later `new_entry` with `optionId`; that stages the meal for HITL confirm before `log_meal`.

## Outcomes

Blocking, at most one: `clarify_food`, `clarify_portion`, `confirm_log`, `confirm_correction`, `confirm_delete`.

Clarify pending payloads carry a **reason** (and `manualLog` / `freeTextGrams`). Candidate labels live in working memory, not in tap chips.

Non-blocking: `suggestionOptions`, `memoryProposals` (client applies them), or a chat reply with no pending action.

`confirm_log` and suggestions may both be present.

Primary diary tools: `new_entry` (stage log), `edit_entry` (one item via `confirm_correction`), `delete_entry` (whole entry via `confirm_delete`), `repeat_prior_meal`.
