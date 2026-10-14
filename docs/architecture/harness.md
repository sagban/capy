# LangGraph harness architecture

Hosted on **Python Firebase Functions (2nd gen)**. Meal chat is one Vertex Gemini turn with typed tools, then deterministic execution. USDA key lives in Secret Manager (`USDA_FDC_API_KEY`). There is no skill router and no phrase list.

Manual Log in the iOS app is the non-AI escape hatch. Offline unit tests use `CAPY_MOCK_AGENT=1`, which scripts `model_turn` and skips the phrase model. The validator still runs.

## Graph

```text
START -> ingest -> dispatch
dispatch --typed action--> execute
dispatch --no action-----> model_turn
model_turn --tool calls--> execute
model_turn --text only---> phrase
model_turn --bad args---> model_turn   (once, then resolve the raw utterance)
model_turn --infra x2---> respond      (agent_unavailable)
execute --> phrase --> respond -> END
```

| Node | File | Job |
|------|------|-----|
| ingest | `graph.py` | Validate the request. Build the context pack (last 8 turns, 14-day diary with entry ids, slot budgets, usual foods, draft, queue, suggestions). |
| dispatch | `graph.py` | Branch on `action` only. It does not read the utterance. |
| model_turn | `agent.py` | One Gemini call with every tool. All function calls are kept. `lookup_menu` may run once before the terminal calls. |
| execute | `harness/execute.py` | Run `resolve_meal`, `edit_draft`, `log_from_suggestion`, `compose_suggestions`, `repeat_prior_meal`, `correct_entry`, `save_memory`. |
| phrase | `harness/phrase.py` | Shows the model's own sentence. No second model call. If a tool returned cards and the model wrote nothing, a factual line is filled from those cards. |
| respond | `graph.py` | `normalize_outcome()`. Infra failure is `warnings: ["agent_unavailable"]` and an empty message. |

## Resolve

`harness/resolve.py`, portions in `harness/portions.py`.

1. Queries: food query, brand + query, model aliases, singular. At most 5. No miss cache.
2. `food_search.search_foods`. USDA search also asks for Survey (FNDDS). `high` commits. `medium` with 2 or more hits clarifies the top 3. Otherwise the next query.
3. Web: one grounded call. Kept only with a citation URL and an Atwater check (`|kcal - (4P+4C+9F)| <= 15%` and kcal per 100 g ≤ 900). `source=web`.
4. Web fails: `clarify_food` with a Manual Log button. The model does not invent a density.
5. Portion: explicit grams, or g/ml/oz/tsp/tbsp/cup at the `Units.swift` factors, or the food's own USDA/branded measures. Otherwise the reply asks how much, in text.
6. The first item that still needs the user pauses the turn. `resolveQueue` holds resolved items, the pending draft, and the remaining drafts. The next message continues it. The whole turn stops at 45 seconds; a late item is asked about in text.

## Suggestions

`harness/meal_budget.py`. A suggestion is a normal meal for that slot, not the day's remainder.

- Stated budget if the model passes one.
- Else the median kcal and protein of that slot when 3 or more days exist in the diary.
- Else remaining kcal and protein split across this meal and later main meals not yet logged. Breakfast and lunch that were never logged are missed, not still ahead, so dinner gets what is left.
- Always capped at remaining kcal. Remaining at or below 0 makes the budget 0 and every option `over`.

After resolve: drop an option that hits an allergy, a dislike, or a food family already logged today. `within` means kcal at or under the slot budget and protein at least 90% of the slot protein. There is no calorie floor. `over` is shown. Options are not a pending action. Logging one is a `pick_option` action or a later `log_from_suggestion` call.

## Outcomes

Blocking, at most one: `clarify_food`, `clarify_portion`, `confirm_log`, `confirm_correction`.

Non-blocking: `suggestionOptions`, `memoryProposals` (client applies them), or a chat reply with no pending action.

`confirm_log` and suggestions may both be present.
