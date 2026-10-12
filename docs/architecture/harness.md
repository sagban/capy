# LangGraph harness architecture

Hosted on **Python Firebase Functions (2nd gen)**. Gemini provides structured output only. Keys live in Secret Manager.

## Graph (V1)

```text
START
  → interpret_intent      # Gemini structured: log | suggest | correct | clarify | set_pref
  → resolve_foods         # tool: search_food (local cache ids preferred; USDA on miss)
  → propose_portions      # Gemini or rules: grams / ambiguous → clarify
  → (optional) clarify    # one clarifying question; never silent gram guess
  → emit_structured       # response DTO — no macros
END
```

Suggestion **verification and ranking run on device** (Swift Core). The harness may propose candidate meal template ids / food+grams; Swift verifies ±10% and abstains.

## Tools surface

| Tool | Owner | Notes |
|------|-------|-------|
| `search_food` | Functions | Local catalog + USDA Foundation/SR Legacy fallback |
| `propose_meal` | Functions | Candidate foods/templates + portions; not final macros |
| `calc_macros` | **Swift (source of truth)** | Functions may mirror for tests only; UI must use Swift |

## State (conceptual)

- `messages` / latest user utterance
- `intent`
- `candidates[]` — food_id or name, grams?, confidence
- `clarifying_question?`
- `memory_snapshot` — explicit prefs only (see API contracts)
- `error` / `abstain_hint`

## Policies

- Max **2** verify retries on device with named rejection reasons, then abstain
- Ambiguous portion → **one** clarifying question
- No coach / motivation nodes
- Quiet / Guided / Full Assist initiation is an **iOS policy** (FR-7); harness stays reactive unless called

## Memory snapshot

Client sends only explicit user-managed data: preferences, dislikes, allergies, diets, regular meal ids, recent corrections. No hidden inferred memories.
