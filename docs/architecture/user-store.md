# Server user store (Firestore)

Firestore store for profile, diary, library, and the Capy thread. `useServerContext: true` loads it for a turn. `false` uses the snapshots on the request.

## Paths

| Path | Purpose |
|------|---------|
| `users/{uid}` | Profile: targets, meal plan, prefs, assistance, long-term notes |
| `users/{uid}/days/{dayKey}/entries/{entryId}` | One meal log (embedded `items[]`) |
| `users/{uid}/library/{itemId}` | User library food / recipe / meal (soft-delete via `deleted`) |
| `users/{uid}/clientMutations/{clientMutationId}` | Idempotency index for meal + library writes |
| `users/{uid}/threads/{threadId}` | Capy thread head: summary, rolling `recentTurns` (harness), `workingMemory`, `nextSeq` |
| `users/{uid}/threads/{threadId}/messages/{messageId}` | Durable chat archive (every turn) |

Client Firestore rules remain **deny-all**; only Cloud Functions (Admin SDK) read/write.

## Profile document (`users/{uid}`)

```json
{
  "schemaVersion": 1,
  "timezone": "America/Chicago",
  "dailyTarget": { "calories": 2000, "proteinG": 140, "carbsG": 200, "fatG": 65 },
  "mealPlan": [{ "name": "Meal 1", "sortOrder": 0, "enabled": true }],
  "likes": [],
  "dislikes": [],
  "allergies": [],
  "diets": [],
  "assistanceLevel": "fullAssist",
  "responseStyle": "balanced",
  "longTermMemory": [{ "id": "mem_1", "text": "…" }],
  "updatedAt": "2026-10-16T12:00:00Z"
}
```

Missing doc → defaults applied on read (`agent/user_store.py`).

## Thread document (`users/{uid}/threads/{threadId}`)

```json
{
  "threadId": "default",
  "summary": "user: logged lunch · capy: …",
  "recentTurns": [
    { "role": "user", "text": "chicken and rice" },
    { "role": "assistant", "text": "logged — 520 cal left." }
  ],
  "workingMemory": { "pendingIntent": "confirm_log", "pendingAction": { } },
  "nextSeq": 42,
  "updatedAt": "2026-10-16T12:00:00Z"
}
```

`recentTurns` + `summary` are the **rolling window** (last 12 turns) used by the harness. They are trimmed in place; overflow is folded into `summary`.

## Message archive (`…/messages/{messageId}`)

```json
{
  "messageId": "uuid",
  "role": "user",
  "text": "chicken and rice",
  "seq": 41,
  "createdAt": "2026-10-16T12:00:00Z"
}
```

Every user/assistant turn is appended here (`seq` monotonic per thread). `patch_thread` with `reset: true` deletes this subcollection and writes a fresh thread document (`summary` empty, `recentTurns` empty, `nextSeq` 0).

`interpret_meal` / `patch_thread` archive new turns, update the rolling window + `workingMemory`, and return a **page** of messages for the client.

### `get_thread` contract

**Request** (callable `get_thread`):

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `threadId` | string | `"default"` | Thread to read |
| `limit` | int | `12` | Page size (max 50) |
| `cursor` | string? | omit | `messageId` of the **oldest** message the client already has; returns older messages |

**Response**:

```json
{
  "conversation": {
    "threadId": "default",
    "summary": "…",
    "workingMemory": null,
    "recentTurns": []
  },
  "messages": [
    { "messageId": "…", "role": "user", "text": "…", "createdAt": "…", "seq": 30 }
  ],
  "pageInfo": {
    "hasMore": true,
    "nextCursor": "messageId-of-oldest-in-this-page"
  }
}
```

- **Initial load** (no `cursor`): newest `limit` messages, chronological order.
- **Scroll up** (`cursor` = previous `pageInfo.nextCursor`): next older page.
- `pageInfo.nextCursor` is only set when `hasMore` is true; pass it as the next `cursor`.
- `conversation.recentTurns` is empty on the wire. The harness reads `recentTurns` from the thread document.

`interpret_meal` (with `useServerContext`) adds the same `messages` + `pageInfo` shape after a successful turn (latest window).

### `patch_thread` contract

**Request** (callable `patch_thread`). One of these fields is required:

| Field | Type | Meaning |
|-------|------|---------|
| `threadId` | string | Default `"default"` |
| `assistantText` | string | Append one assistant message and return the latest page |
| `dayRollover` | object | `{ "previousDayKey", "mealCount" }` folded into `summary` |
| `clearWorkingMemory` | bool | With `assistantText`, drop `workingMemory` |
| `reset` | bool | Must be JSON `true`. Deletes the message archive and clears the rolling window. Other fields on the same request are ignored |

**Response** matches `get_thread`: `conversation`, `messages`, `pageInfo`. After `reset: true`, `messages` is empty and `pageInfo.hasMore` is false.

## Diary entry document

```json
{
  "entryId": "uuid",
  "dayKey": "2026-10-16",
  "mealSlot": "Meal 2",
  "confirmed": true,
  "clientMutationId": "optional-client-uuid",
  "items": [
    {
      "name": "Egg",
      "grams": 100,
      "foodId": "seed_egg",
      "source": "seed",
      "per100g": { "calories": 155, "proteinG": 13, "carbsG": 1.1, "fatG": 11 },
      "ingredientFamily": "egg"
    }
  ],
  "createdAt": "…",
  "updatedAt": "…"
}
```

Harness context expands each item to a `DiaryEntry` row.

## Library item document (`users/{uid}/library/{itemId}`)

```json
{
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
  "deleted": false,
  "createdAt": "…",
  "updatedAt": "…"
}
```

`kind`: `food` | `recipe` | `meal`. `origin`: `user` | `aiGenerated`. Soft-delete sets `deleted: true`.

## Callables

| Function | Role |
|----------|------|
| `patch_profile` | Merge allowed profile fields |
| `log_meal` | Create/update entry; idempotent via `clientMutationId` |
| `delete_meal` | Soft-delete entry (`deleted: true`); idempotent via `clientMutationId` |
| `upsert_library_item` | Create/replace library doc; idempotent via `clientMutationId` |
| `delete_library_item` | Soft-delete library doc; idempotent via `clientMutationId` |
| `list_library` | List library docs (`includeDeleted` optional) for client merge |
| `list_diary` | List diary meal docs (`includeDeleted` optional) so the iPhone restores from Firestore |
| `interpret_meal` | Pass `useServerContext: true` to load diary/profile/thread/library from Firestore; returns updated `conversation` |
| `get_thread` | Read `users/{uid}/threads/{threadId}` |
| `patch_thread` | Append assistant text, note a day rollover, or `reset: true` to delete the chat |

## Context loader

`agent/context_loader.py` → `load_interpret_request` / `resolve_interpret_request`.

Builds `InterpretMealRequest` for `prepare` → `build_pack` → `semantic_block`. Utterance and `dayKey`/`timezone` come from the client; conversation loads from `users/{uid}/threads/{threadId}` (`agent/thread_store.py`). With `useServerContext`, `libraryContext` loads from `users/{uid}/library` (merged with any client snapshot).

## Recipes collection

Named dishes live in `recipes/{recipeId}` on database `capy`, not in `foodCorpus`. `foodCorpus` holds atomic foods and templates. `scripts/import_seed_food_corpus.py` writes both. A library recipe on the phone is still `users/{uid}/library/{id}`.

## iOS client

- `UserSyncService` queues `log_meal` / `delete_meal` / `patch_profile` / `upsert_library_item` / `delete_library_item` (UserDefaults), flushes on network + app active.
- Diary pull: `list_diary` on launch, foreground, and when Food Log is selected. Firestore replaces the local diary. A meal still queued for `log_meal` or `delete_meal` stays until that flush finishes.
- Library pull: `list_library` on launch / foreground; merge into SwiftData; push local-only rows.
- `InterpretMealRequestDTO.serverContext` sends the utterance, day, `useServerContext`, and a compact `libraryContext`. Chat history syncs through `get_thread`, the `interpret_meal` `conversation`, and `patch_thread`. The phone keeps that transcript in SwiftData (`ChatMessageRecord`), keyed by the signed-in account, and shows that account's saved messages, including older pages, then refreshes them from `get_thread`. Starred messages stay on the phone in `UserDefaults` for that same account; reset clears that account's list and its local transcript.
- Profile push: Settings, goals, meal types, memory sheet, and app launch.
