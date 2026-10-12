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
  "utterance": "chipotle bowl, chicken and rice",
  "timezone": "America/Chicago",
  "dayKey": "2026-10-11",
  "memorySnapshot": {
    "preferences": ["high protein"],
    "dislikes": ["cilantro"],
    "allergies": [],
    "diets": ["vegetarian"],
    "regularTemplateIds": ["tpl_chicken_stirfry"],
    "recentCorrections": [
      { "text": "half the rice", "at": "2026-10-11T12:01:00Z" }
    ]
  },
  "context": {
    "assistanceLevel": "fullAssist",
    "lastIntent": null
  }
}
```

### Response (success)

```json
{
  "intent": "log_meal",
  "candidates": [
    {
      "foodId": "seed_chicken_breast",
      "displayName": "Chicken breast",
      "grams": 150,
      "confidence": 0.82
    },
    {
      "foodId": "seed_white_rice_cooked",
      "displayName": "White rice, cooked",
      "grams": 200,
      "confidence": 0.75
    }
  ],
  "clarifyingQuestion": null,
  "correction": null,
  "suggestedTemplateId": null,
  "assistantMessage": "logged — confirm portions?",
  "warnings": []
}
```

`intent` enum: `log_meal` | `suggest_meal` | `correct_meal` | `clarify` | `update_preference` | `unknown`

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

Note: `per100g` here is **catalog data** from DB/USDA (deterministic), not an LLM invention. The LLM must not invent these fields; the tool fills them after lookup.

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
4. Schema changes require updating this file in the same PR.
