# API contracts (Pydantic ↔ Swift Codable)

All callable endpoints require a Firebase **ID token**. Responses **must not** include trusted calorie/PCF totals.

Base: Firebase Callable (or HTTPS function) on the active project.

## Auth

```http
Authorization: Bearer <Firebase ID token>
```

Reject unauthenticated requests. App Check: document in Phase 0; enforce in Phase 3+.

## `interpretMeal` (primary)

### Request

```json
{
  "utterance": "make the rice half",
  "timezone": "America/Chicago",
  "dayKey": "2026-10-12",
  "preferenceContext": {
    "likes": ["high protein"],
    "dislikes": ["cilantro"],
    "allergies": ["peanut"],
    "diets": ["vegetarian"]
  },
  "diaryContext": {
    "today": [],
    "previousDays": [],
    "remaining": { "calories": 820, "proteinG": 60, "carbsG": 90, "fatG": 25 },
    "remainingSource": "clientComputed"
  },
  "longTermMemory": [
    { "id": "mem_1", "text": "Usually eats dinner after 9pm on weekdays" },
    { "id": "mem_2", "text": "No microwave at work" }
  ],
  "conversation": {
    "summary": "User logging lunch; awaiting portion confirm on rice.",
    "recentTurns": [
      { "role": "user", "text": "rice and dal" },
      { "role": "assistant", "text": "quick check on the rice" }
    ],
    "workingMemory": {
      "pendingIntent": "clarify",
      "clarifyingQuestion": "Was that about a cup of rice, or half?",
      "candidates": [
        { "foodId": "usda_168878", "displayName": "Rice, white, long-grain, regular, enriched, cooked", "grams": null }
      ]
    }
  },
  "context": { "assistanceLevel": "fullAssist", "lastIntent": "clarify" },
  "memorySnapshot": {
    "preferences": ["high protein"],
    "dislikes": ["cilantro"],
    "allergies": ["peanut"],
    "diets": ["vegetarian"],
    "regularTemplateIds": ["tpl_chicken_stirfry"],
    "recentCorrections": []
  }
}
```

`memorySnapshot` remains for #37 compatibility; clients should prefer `preferenceContext` + `diaryContext` + `longTermMemory` + `conversation`.

### Response (success)

```json
{
  "intent": "log_meal",
  "candidates": [
    {
      "foodId": "usda_171140",
      "displayName": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, cooked, braised",
      "grams": 150,
      "confidence": 0.82
    }
  ],
  "clarifyingQuestion": null,
  "correction": null,
  "suggestedTemplateId": null,
  "assistantMessage": "logged — confirm portions?",
  "warnings": [],
  "memoryProposals": []
}
```

`intent` enum: `log_meal` | `suggest_meal` | `correct_meal` | `clarify` | `update_preference` | `update_memory` | `unknown`

### Response (memory update)

```json
{
  "intent": "update_memory",
  "candidates": [],
  "assistantMessage": "saved that for later",
  "memoryProposals": [
    { "action": "add", "text": "Strength trains on Tuesday evenings" }
  ],
  "warnings": []
}
```

`memoryProposals.action`: `add` | `update` | `delete`. Client applies automatically; user can edit in Capy Memory sheet.

### Response (needs clarification)

```json
{
  "intent": "clarify",
  "candidates": [],
  "clarifyingQuestion": "Was that about a cup of rice, or half?",
  "assistantMessage": "quick check on the rice",
  "warnings": ["ambiguous_portion"]
}
```

## Tools (request-scoped)

| Tool ID | Returns |
|---------|---------|
| `get_user_preferences` | likes / dislikes |
| `get_dietary_restrictions` | allergies + diets |
| `get_long_term_memory` | durable Muse-style notes |
| `get_today_food_log` | today's confirmed entries |
| `get_previous_food_logs` | last N day summaries |
| `search_food` | catalog / USDA hits + `per100g` |
| `propose_meal` | template / food+grams candidates |
| `calc_macros` | **Swift only** (source of truth) |

## `searchFood`

### Request

```json
{ "query": "paneer", "limit": 10 }
```

### Response

```json
{
  "results": [
    {
      "foodId": "seed_paneer",
      "displayName": "Paneer",
      "source": "seed",
      "per100g": { "calories": 265, "proteinG": 18, "carbsG": 1.2, "fatG": 20 }
    }
  ],
  "cache": "hit"
}
```

Note: `per100g` here is **catalog data** from DB/USDA (deterministic), not an LLM invention. The LLM must not invent these fields; the tool fills them after lookup. Same-day miss cache: repeated empty queries short-circuit for the day.

## Error shape

```json
{
  "code": "unauthenticated" | "invalid_argument" | "upstream" | "not_found",
  "message": "human-safe string"
}
```

## Client rules

1. Decode into Swift Codable DTOs mirroring this doc.
2. Run `Core` macros on confirmed grams + Food per100g.
3. Discard any unexpected macro fields from model free text.
4. Pack conversation window (summary + last 12 turns + workingMemory) and long-term memory notes each call.
5. Schema changes require updating this file in the same PR.
