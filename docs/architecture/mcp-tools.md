# MCP tool catalog

Server implementation: [`mcp_server/capy_mcp/server.py`](../../mcp_server/capy_mcp/server.py). Each tool POSTs to the matching Firebase Callable with the host's bearer token.

## `interpret_meal`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `utterance` | string | yes | User message (max 80 chars server-side) |
| `day_key` | string | yes | Diary day key (`YYYY-MM-DD`) |
| `timezone` | string | no | IANA tz (default `UTC`) |
| `thread_id` | string | no | Capy thread (default `default`) |
| `use_server_context` | boolean | no | Load profile/diary/thread from Firestore (default `true`) |

**Returns:** JSON `InterpretMealResponse` — `intent`, `assistantMessage`, `suggestionOptions`, `pendingAction`, `messages`, `pageInfo`, etc. See [api-contracts.md](api-contracts.md).

## `log_meal`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `day_key` | string | yes | |
| `meal_slot` | string | yes | |
| `items` | array | yes | `{ name, grams, foodId?, source?, per100g?, ingredientFamily? }` |
| `entry_id` | string | no | Upsert id |
| `client_mutation_id` | string | no | Idempotency key |
| `confirmed` | boolean | no | Default `true` |

**Returns:** `{ "dayKey", "entryId" }`.

## `patch_profile`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `patch` | object | yes | Subset of profile fields (see [user-store.md](user-store.md)) |

**Returns:** `{ "profile": { ... } }`.

## `upsert_library_item`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `item` | object | yes | Library row (`id`, `name`, `kind`, macros, `ingredients`, …) |
| `client_mutation_id` | string | no | Idempotency key |

**Returns:** `{ "id" }`.

## `delete_library_item`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | yes | Library item id |
| `client_mutation_id` | string | no | Idempotency key |

**Returns:** `{ "id" }`.

## `list_library`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `include_deleted` | boolean | no | Default `false` |

**Returns:** `{ "items": [ … ] }`.

## `get_thread`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `thread_id` | string | no | Default `default` |
| `limit` | int | no | Page size (default 12, max 50) |
| `cursor` | string | no | `messageId` for older page |

**Returns:** `{ conversation, messages, pageInfo }` — see [user-store.md](user-store.md#get_thread-contract).

## `patch_thread`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `assistant_text` | string | no* | Assistant line to append |
| `thread_id` | string | no | Default `default` |
| `clear_working_memory` | boolean | no | Clear open confirm/clarify state |
| `previous_day_key` | string | no* | With `meal_count` for day rollover note |
| `meal_count` | int | no* | |

\*Requires `assistant_text` or both `previous_day_key` and `meal_count`.

**Returns:** Same shape as `get_thread` (latest window after mutation).

## `exchange_access_token`

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `firebase_id_token` | string | yes | Fresh Firebase ID token |

**Returns:** `{ accessToken, tokenType, expiresIn, uid }`.
