# API contracts (Pydantic ↔ Swift Codable)

All callable endpoints require a Firebase **ID token**. Responses **must not** include trusted calorie/PCF totals.

Base: Firebase Callable (or HTTPS function) on the active project.

## Auth

```http
Authorization: Bearer <Firebase ID token | Capy access token>
```

- **iOS:** Firebase SDK callables (ID token attached automatically).
- **MCP token page:** `GET /authenticate` on `capy-mcp`. `POST /authenticate` with `{ email, password }` returns `{ accessToken, tokenType, expiresIn, mcpUrl }` for an MCP client. The iPhone app mints the same token from Settings.
- **HTTP / MCP / Alexa:** Callable HTTP with `Authorization: Bearer`, or mint a 1h access token via `exchange_access_token`.

MCP tools: [mcp-tools.md](mcp-tools.md). The bearer is a Firebase ID token or the one-hour token from `exchange_access_token`.

Reject unauthenticated requests. App Check is not enforced.

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

Returns `{ "dayKey", "entryId" }`. Each item needs `name`, `grams`, and `per100g`. Replays with the same `clientMutationId` return the original ids.

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

`"useServerContext": true` loads diary, profile, thread, and library from Firestore. The iPhone sends `utterance`, `timezone`, `dayKey`, optional `threadId`, that flag, and a compact `libraryContext` (merged with the server library). The thread is `users/{uid}/threads/{threadId}`. The response includes the updated `conversation`. `false` uses the snapshots on the request.

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

Clients send preferences on `preferenceContext`, the diary on `diaryContext`, notes on `longTermMemory`, and the thread on `conversation`. `memorySnapshot` is an extra copy of preferences and recent corrections.

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

`suggestionOptions` are stored on `workingMemory.lastSuggestionOptions` for the next turn. The Capy tab shows them as chat, not cards. Totals are summed from hits the model already looked up and portioned. Logging one is a later `write_food_entry`. The first in-app `write_food_entry` returns pending `confirm_log`. The confirmed call writes it. `confirm_correction` uses the same sheet.

`confirm_log` payload `resolvedItems`: `{ foodId, displayName, grams, per100g, source, citationUrl?, portionLabel? }`. `source`: `catalog` | `usda` | `usda_branded` | `web` | `diary`. `web` is a cited per-100g density that passed the Atwater check; the web worker may convert a cited serving to per 100 g. Code multiplies grams.

`clarify_food` / `clarify_portion` carry `reason`, and may set `freeTextGrams` or `manualLog`. Candidate names are in `workingMemory.resolveQueue`, not tap chips. The next utterance continues resolve.

`confirm_correction` payload: `entryId`, `itemIndex`, `correctionOp` `set_amount` | `replace` | `remove`, plus `resolvedItems` unless the op is `remove`.

`confirm_delete` payload: `entryId`, `dayKey`, optional `reason` (label for the confirm sheet). Client confirms, then calls `delete_meal` to soft-delete in Firestore.

`assistantMessage` may be empty when the confirm sheet carries the turn. Prefer the model's human chat prose; if that draft is empty or is a tool/ResolvedItem dump, the harness drops the dump and falls back to a short factual line (e.g. confirm_log item names or suggestion totals). Structured fields (`pendingAction`, `candidates`, `suggestionOptions`) are validated separately and never shown as chat. `warnings` includes `agent_unavailable` only after a model or network failure; the client shows Retry and does not invent a sentence.

`memoryProposals.action`: `add` | `update` | `delete`. The harness adds one when the utterance starts with "remember" or "forget". The client applies it in the Capy Memory sheet. There is no confirm step for a note.

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

## Shared tools

The in-app model and MCP use the same functions. Names and when-to-use text live in `functions/agent/tools/`. Layout: [harness.md](harness.md).

| Tool | Effect |
|------|--------|
| `search_catalog` | Seed-catalog hits. Does not log. |
| `search_usda` | USDA FoodData Central hits, in FDC order. Does not log. |
| `search_library` | Strict match on the saved library. The wrapper loads the rows. Does not log. |
| `lookup_barcode` | Open Food Facts for one GTIN. Miss is `{ "found": false }`. Does not log. |
| `portion_to_grams` | `{grams, label}` from a quantity, a unit, and the hit's measures. `{unmapped: true}` when the unit is unknown. |
| `get_diary` | `{dayKey, entries, remaining}`. |
| `write_food_entry` | Writes one entry. `kind` is `food`, `recipe`, or `meal`. Requires `name`, `grams`, and `per100g`. `entry_id` replaces that one entry. The iPhone callable that can still send an item list is `log_meal`. |
| `delete_food_entry` | Deletes one `entry_id` on `day_key`. The iPhone callable is `delete_meal`. |

Google Search grounding is on the same Vertex `generate_content` call. It is not a harness tool. Model: Gemini 3+ (`VERTEX_GEMINI_MODEL`, default `gemini-3.5-flash`) at location `global`.

The in-app wrapper marks a hit that breaks a diet or names an allergy with `conflict` (`diet` or `allergy`) and still returns it. The first in-app `write_food_entry` or `delete_food_entry` stages a confirm and does not write. MCP writes on the call. Displayed totals are computed on the iPhone from confirmed grams and per-100g.

Firebase callables in `main.py` are the iOS edge. `interpret_meal` enters the graph. `log_meal`, `delete_meal`, barcode, and library callables call `user_api` directly. Tools call those same `user_api` functions. They do not call the callable handlers.

### Search hit shape

`search_catalog`, `search_usda`, and `search_library` return `{ "source", "hits": [ { "foodId", "displayName", "source", "per100g", "family", "measures" } ] }`. `source` is `catalog`, `usda`, or `library`. Catalog hits stay in seed order. USDA hits stay in FoodData Central order.

`lookup_barcode` returns the Open Food Facts dict: a hit with `found: true`, or `{ "found": false }`.

The tool functions return the source's hits. Inside the iPhone `interpret_meal` callable, a conflicting hit stays in that list with `conflict` set to `diet` or `allergy`. MCP lookups return the source result with no `conflict` field.

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
