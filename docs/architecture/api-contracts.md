# API contracts (Pydantic ↔ Swift Codable)

All callable endpoints require a Firebase **ID token**. Responses **must not** include trusted calorie/PCF totals.

Base: Firebase Callable (or HTTPS function) on the active project.

## Auth

```http
Authorization: Bearer <Firebase ID token | Cappy access token>
```

- **iOS:** Firebase SDK callables (ID token attached automatically).
- **HTTP / MCP / Alexa:** Callable HTTP with `Authorization: Bearer`, or mint a 1h access token via `exchange_access_token`.

Full flow: [external-auth.md](external-auth.md). MCP tools: [mcp-tools.md](mcp-tools.md).

Reject unauthenticated requests. App Check: document in Phase 0; enforce in Phase 3+.

### `exchange_access_token` (callable, unauthenticated)

```json
{ "firebaseIdToken": "<from Firebase Auth sign-in>" }
```

→ `{ "accessToken", "tokenType": "Bearer", "expiresIn": 3600, "uid" }`

## Server user store

Firestore layout and profile fields: [user-store.md](user-store.md).

### `patch_profile` (callable)

Authenticated merge into `users/{uid}`. Allowed keys: `timezone`, `dailyTarget`, `mealPlan`, `likes`, `dislikes`, `allergies`, `diets`, `assistanceLevel`, `responseStyle`, `longTermMemory`.

### `log_meal` (callable)

```json
{
  "dayKey": "2026-10-16",
  "mealSlot": "Meal 2",
  "entryId": "optional-uuid",
  "clientMutationId": "optional-idempotency-key",
  "confirmed": true,
  "items": [
    {
      "name": "Egg",
      "grams": 50,
      "foodId": "seed_egg",
      "source": "seed",
      "per100g": { "calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11 }
    }
  ]
}
```

Returns `{ "dayKey", "entryId" }`. Replays with the same `clientMutationId` return the original ids.

### `delete_meal` (callable)

```json
{
  "dayKey": "2026-10-16",
  "entryId": "uuid",
  "clientMutationId": "optional-idempotency-key"
}
```

Soft-deletes `users/{uid}/days/{dayKey}/entries/{entryId}` (`deleted: true`, `confirmed: false`). Returns `{ "dayKey", "entryId" }`. Idempotent via `clientMutationId` like `log_meal`.

### `upsert_library_item` (callable)

```json
{
  "clientMutationId": "optional-idempotency-key",
  "item": {
    "id": "uuid",
    "name": "Gym Bowl",
    "kind": "meal",
    "origin": "user",
    "detail": "",
    "calories": 520,
    "proteinG": 40,
    "carbsG": 45,
    "fatG": 18,
    "servingGrams": 350,
    "sourceFoodId": "",
    "ingredients": [],
    "createdAt": "2026-10-19T12:00:00Z"
  }
}
```

Writes `users/{uid}/library/{id}`. Returns `{ "id" }`. Idempotent via `clientMutationId`.

### `delete_library_item` (callable)

```json
{
  "id": "uuid",
  "clientMutationId": "optional-idempotency-key"
}
```

Soft-deletes `users/{uid}/library/{id}` (`deleted: true`). Returns `{ "id" }`.

### `list_library` (callable)

```json
{ "includeDeleted": false }
```

→ `{ "items": [ /* library docs */ ] }` for client restore/merge.

### `lookup_barcode` (callable)

Exact GTIN → Open Food Facts product for the Manual Log barcode scanner. Server looks up OFF; iOS scales `per100g` to the chosen portion (same as catalog hits). Incomplete nutrition → miss (never invent macros).

```json
{ "gtin": "3017620422003" }
```

Hit:

```json
{
  "found": true,
  "foodId": "off_3017620422003",
  "displayName": "Nutella",
  "brand": "Ferrero",
  "per100g": { "calories": 539, "proteinG": 6.3, "carbsG": 57.5, "fatG": 30.9 },
  "servingGrams": 15,
  "servingLabel": "15 g",
  "source": "open_food_facts"
}
```

Miss / unusable product:

```json
{ "found": false }
```

`servingGrams` / `servingLabel` are optional when OFF has no parseable serving. `gtin` must be at least 8 digits (non-digits stripped). UPC-A ↔ EAN-13 leading-zero variants are tried.

### `interpretMeal` server context

Set `"useServerContext": true` on the interpret request to build diary/profile/thread/library from Firestore instead of inline snapshots. iOS encodes `utterance`, `timezone`, `dayKey`, optional `threadId`, `useServerContext`, and a compact `libraryContext` snapshot (merged with server library). Conversation is stored at `users/{uid}/threads/{threadId}`; `interpret_meal` returns an updated `conversation` on success. Omit or `false` to keep the legacy client snapshot.

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
    // each item: { name, mealSlot, grams, entryId, itemIndex, foodId, source, per100g, ingredientFamily }
    // previousDays covers 14 days so slot medians and usual foods can be computed
    "remaining": { "calories": 820, "proteinG": 60, "carbsG": 90, "fatG": 25 },
    "remainingSource": "clientComputed",
    "mealPlan": [
      { "name": "Meal 1", "sortOrder": 0, "enabled": true },
      { "name": "Meal 2", "sortOrder": 1, "enabled": true },
      { "name": "Meal 4", "sortOrder": 3, "enabled": true }
    ]
  },
  "longTermMemory": [
    { "id": "mem_1", "text": "Usually eats dinner after 9pm on weekdays" },
    { "id": "mem_2", "text": "No microwave at work" }
  ],
  "conversation": {
    "threadId": "default",
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
  "context": { "assistanceLevel": "fullAssist", "responseStyle": "balanced", "lastIntent": "clarify" },
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

There is no `action` field. Follow-ups are the next `utterance`. Clarify labels live in `workingMemory.resolveQueue` for the model, not as UI chips.

`conversation.threadId` defaults to `"default"` (LangGraph checkpoint thread is `{uid}:{threadId}`).

`memorySnapshot` remains for #37 compatibility; clients should prefer `preferenceContext` + `diaryContext` + `longTermMemory` + `conversation`.

`conversation.workingMemory` also carries `resolveQueue`, `lastSuggestionOptions`, and `draftLog`. With `useServerContext`, the server persists `workingMemory` on `users/{uid}/threads/{threadId}` and returns the updated `conversation` on `interpret_meal`.

`context.responseStyle` (profile + interpret request): user-facing **Reply style** dial — `precise`, `balanced` (default), `creative`. Server maps to Gemini sampling (`precise` → 0.2, `balanced` → 0.5, `creative` → 0.8) and appends that style’s instruction block to the meal agent system prompt for the turn (not all three options). Invalid/missing values normalize to `balanced`.

`context.assistanceLevel` (profile + interpret request): user-facing **Assistance** dial — `fullAssist` (default), `guided`, `quiet`. Server appends that level’s instruction block to the meal agent system prompt for the turn (not all three options). Invalid/missing values normalize to `fullAssist`.

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

`suggestionBudget` (optional, on suggest): `{calories, proteinG?, carbsG?, fatG?}` for that meal slot (explicit `budget` on the tool, else median for the slot when history allows, else plan-position weighted defaults, optionally scaled by `appetite`). Each field is a ceiling against remaining, not a target to fill.

`pendingAction.type`: `clarify_portion` | `clarify_food` | `confirm_log` | `confirm_correction` | `confirm_delete` | null

`suggestionOptions` are stored for the next turn (`workingMemory.lastSuggestionOptions`). The Capy tab does not render them as cards. Totals are harness-computed. Logging one is a later `new_entry` call with `optionId` (and optional `ops`), which stages the meal for human-in-the-loop confirm (`confirm_log`). `confirm_correction` also uses that sheet.

`confirm_log` payload `resolvedItems`: `{ foodId, displayName, grams, per100g, source, citationUrl?, portionLabel? }`. `source`: `catalog` | `usda` | `usda_branded` | `web` | `diary`. `web` is a cited per-100g density that passed the Atwater check; the web worker may convert a cited serving to per 100 g. Code multiplies grams.

`clarify_food` / `clarify_portion` carry `reason`, and may set `freeTextGrams` or `manualLog`. Candidate names are in `workingMemory.resolveQueue`, not tap chips. The next utterance continues resolve.

`confirm_correction` payload: `entryId`, `itemIndex`, `correctionOp` `set_amount` | `replace` | `remove`, plus `resolvedItems` unless the op is `remove`.

`confirm_delete` payload: `entryId`, `dayKey`, optional `reason` (label for the confirm sheet). Client confirms, then calls `delete_meal` to soft-delete in Firestore.

`assistantMessage` may be empty when the confirm sheet carries the turn. Prefer the model's human chat prose; if that draft is empty or is a tool/ResolvedItem dump, the harness drops the dump and falls back to a short factual line (e.g. confirm_log item names or suggestion totals). Structured fields (`pendingAction`, `candidates`, `suggestionOptions`) are validated separately and never shown as chat. `warnings` includes `agent_unavailable` only after a model or network failure; the client shows Retry and does not invent a sentence.

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
| `new_entry` | Stage a new meal entry for HITL `confirm_log`: resolve `items`, edit with `ops`, or start from `optionId` (stored suggestion). Catalog/USDA search and portions run in code; optional item `portionMacros` + `citationUrl` (menu macros for that quantity+unit) commits as `web`/`estimate` when Atwater checks pass. |
| `compose_suggestions` | Non-blocking chat suggestions. Optional `appetite` (`light` \| `normal` \| `hearty`) scales the guide; optional `budget` sets an explicit ceiling. Every item needs a household serving (tbsp, cup, piece), not leftover calories as oil. Restaurant drafts should set `venue`/`brandOrVenue` and pass cited `portionMacros` (USDA is skipped for venue items). |
| `repeat_prior_meal` | Copy diary rows by `entryId`. |
| `edit_entry` | `confirm_correction` for one `entryId` + `itemIndex` (`set_amount` \| `replace` \| `remove`). |
| `delete_entry` | `confirm_delete` for a whole `entryId` (optional `dayKey`). User confirms, then `delete_meal` writes Firestore. |
| `save_memory` | `memoryProposals`. Can accompany any other tool. |

The meal model also has **Google Search grounding** on the same Vertex `generate_content` call (not a harness tool). Requires Gemini 3+ (`VERTEX_GEMINI_MODEL`, default `gemini-3.5-flash`) at Vertex location `global` — Gemini 2.5 rejects mixing `google_search` with function tools.

Tools are LangChain `@tool` functions in `functions/agent/harness/tools/registry.py`. Executors live in `jobs.py`. Gemini sees those descriptions and JSON Schema (including when-to-use guidance and examples in each tool docstring). Request context is `InjectedToolArg`, not a model parameter. The system prompt in `functions/agent/llm/prompt.py` covers persona, context-pack grounding, trust boundaries, Google Search, orchestration, assistance level, and global food rules — not per-tool parameter playbooks.

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
