# LangGraph harness architecture

Hosted on **Python Firebase Functions (2nd gen)**. Gemini intent runs on **Vertex AI** (ADC, project `capy-dogfood`); heuristics cover goldens / Vertex outages. USDA key lives in Secret Manager (`USDA_FDC_API_KEY`).

## Graph (V1)

```text
START
  → interpret_intent      # Gemini or heuristics: log | suggest | correct | clarify | update_memory | …
  → tool_router           # prefs / diet / ltm / diary / search / propose
  → resolve_and_emit      # candidates + optional memoryProposals — no macros
END
```

Suggestion **verification and ranking run on device** (Swift Core). The harness may propose candidate meal template ids / food+grams; Swift verifies ±10% and abstains.

## Tools surface

| Tool | Owner | Notes |
|------|-------|-------|
| `get_user_preferences` | Functions (request context) | Explicit likes/dislikes |
| `get_dietary_restrictions` | Functions (request context) | Allergies + diets |
| `get_long_term_memory` | Functions (request context) | Muse-style durable notes |
| `get_today_food_log` | Functions (request context) | Today's confirmed entries |
| `get_previous_food_logs` | Functions (request context) | Prior day summaries |
| `search_food` | Functions | Seed catalog + USDA Foundation/SR Legacy fallback; same-day miss cache |
| `propose_meal` | Functions | Candidate foods/templates + portions; not final macros |
| `calc_macros` | **Swift (source of truth)** | Functions must not own UI macros |

## State (conceptual)

- Latest user utterance + conversation summary / recentTurns / workingMemory
- `intent`
- `candidates[]` — food_id or name, grams?, confidence
- `clarifying_question?`
- `longTermMemory[]` + `memoryProposals[]`
- `preferenceContext` / `diaryContext` (clientComputed remaining)
- `error` / `abstain_hint`

## Policies

- Max **2** verify retries on device with named rejection reasons, then abstain
- Ambiguous portion → **one** clarifying question
- No coach / motivation nodes
- Quiet / Guided / Full Assist initiation is an **iOS policy** (FR-7); harness stays reactive unless called
- Long-term memory proposals never include macros

## Memory layers

| Layer | Owner | Notes |
|-------|-------|-------|
| Prefs / diet | SwiftData `UserPreference` | Settings; never LLM-inferred into this bucket |
| Diary | SwiftData `MealEntry` | Tools for today / previous — not chat text |
| Long-term notes | SwiftData `LongTermMemoryNote` | Muse-style; editable in Capy Memory sheet |
| Conversation window | `ConversationThread` + turns | Last 12 + rolling summary |
| Working slot | Last assistant structured payload | Pending clarify / candidates |

Client builds the pack via `ContextBuilder` each `interpretMeal` call.
