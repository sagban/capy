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
  "action": null,
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
    // each item: { name, mealSlot, grams, entryId, itemIndex, foodId, source, per100g, ingredientFamily }
    // previousDays covers 14 days so slot medians and usual foods can be computed
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

`action` is set only by a chip or button: `{ "type": "pick_candidate" | "pick_portion" | "pick_option", "id": "..." }`. When it is set, `utterance` may be empty. The server does not parse free text to recover a tap.

`memorySnapshot` remains for #37 compatibility; clients should prefer `preferenceContext` + `diaryContext` + `longTermMemory` + `conversation`.

`conversation.workingMemory` also carries `resolveQueue`, `lastSuggestionOptions`, and `draftLog`. The client stores the `workingMemory` object from the response and sends it back.

### Response (success / HITL confirm)

```json
{
  "intent": "log_meal",
  "candidates": [
    {
      "foodId": "usda_171140",
      "displayName": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, cooked, braised",
      "grams": 150,
      "confidence": 0.82,
      "source": "usda"
    }
  ],
  "clarifyingQuestion": null,
  "correction": null,
  "suggestedTemplateId": null,
  "assistantMessage": "confirm portions when you’re ready.",
  "warnings": [],
  "memoryProposals": [],
  "pendingAction": {
    "type": "confirm_log",
    "prompt": "confirm portions when you’re ready.",
    "payload": {
      "candidates": [
        {
          "foodId": "usda_171140",
          "displayName": "Chicken, broiler or fryers, breast, skinless, boneless, meat only, cooked, braised",
          "grams": 150,
          "source": "usda"
        }
      ],
      "memoryText": null
    }
  }
}
```

`intent` enum: `log_meal` | `suggest_meal` | `correct_meal` | `clarify` | `update_preference` | `update_memory` | `unknown`

`suggestionBudget` (optional, on suggest): `{calories, proteinG?}` for that meal slot (stated, else the user's typical meal for the slot, else what is left split across this meal and later main meals). It is a ceiling, not a target to fill.

`pendingAction.type`: `clarify_portion` | `clarify_food` | `confirm_log` | `confirm_correction` | null

`suggestionOptions` are not a pending action. Each is `{ id, title, reason, items[{foodId,displayName,grams,source,per100g,portionLabel}], totals, fit: within|over }`. Totals are harness-computed. A "Log this" button sends `pick_option`. The confirm sheet opens only for `confirm_log` or `confirm_correction`.

`confirm_log` payload `resolvedItems`: `{ foodId, displayName, grams, per100g, source, citationUrl?, portionLabel? }`. `source`: `catalog` | `usda` | `usda_branded` | `web` | `diary`. `web` is a cited per-100g density that passed the Atwater check. The model does not multiply grams.

`clarify_food` / `clarify_portion` payload `clarifyOptions`: `{ id, label, foodId?, grams? }`. Portion clarify may set `freeTextGrams` when the food has no household measure. A not-found clarify sets `manualLog`.

`confirm_correction` payload: `entryId`, `itemIndex`, `correctionOp` `set_amount` | `replace` | `remove`, plus `resolvedItems` unless the op is `remove`.

`assistantMessage` may be empty when chips, a sheet, or cards carry the turn. It never contains food ids, tool names, or HTTP details. `warnings` includes `agent_unavailable` only after a model or network failure; the client shows Retry and does not invent a sentence.

`memoryProposals.action`: `add` | `update` | `delete`. The client applies them. There is no `confirm_memory` pause.

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

## Tools the model may call

| Tool | Effect |
|------|--------|
| `resolve_meal` | Log items. Search, web nutrition, and portions run in code. |
| `edit_draft` | Change the open confirm draft. |
| `log_from_suggestion` | Copy a stored option into `confirm_log`. |
| `compose_suggestions` | Non-blocking option cards. Every item needs a quantity and unit. |
| `repeat_prior_meal` | Copy diary rows by `entryId`. |
| `correct_entry` | `confirm_correction` for one `entryId` + `itemIndex`. |
| `lookup_menu` | Menu names only. At most once before `compose_suggestions`. |
| `save_memory` | `memoryProposals`. Can accompany any other tool. |

`search_food`, web nutrition, and `scale_portion` are internal. `scale_portion` requires grams. There is no same-day miss cache. `calc_macros` stays in Swift.

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
4. Pack conversation window (summary + last 12 turns + workingMemory) and long-term memory notes each call.
5. Schema changes require updating this file in the same PR.
