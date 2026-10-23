# MCP tool catalog

Hosted server: [`functions/cloudrun/mcp/host.py`](../../functions/cloudrun/mcp/host.py), mounted at `POST /mcp/` by [`functions/cloudrun/app.py`](../../functions/cloudrun/app.py). Tools run in-process. The caller is the agent: it looks food up, portions it, and writes the diary.

`interpret_meal`, `get_thread`, and `patch_thread` are Firebase callables for the iPhone. They are not tools on this server. `exchange_access_token` is the callable and `POST /exchange_access_token` on the same host.

## `write_food_entry`

Write one diary entry. One call is one food, one recipe, or one meal. Call it again for the next one. Call this after a lookup and `portion_to_grams`, when the user agreed. Do not invent grams or `per100g`. Pass `entry_id` to replace that one entry. Pass the same `client_mutation_id` on a retry so the write happens once. Saving a reusable library row is `upsert_library_item`.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `day_key` | string | yes | Diary day, `YYYY-MM-DD` |
| `meal_slot` | string | yes | Slot name from the user's meal plan |
| `kind` | string | yes | `food`, `recipe`, or `meal` |
| `name` | string | yes | Name of this one entry |
| `grams` | number | yes | Portion weight in grams |
| `per100g` | object | yes | `{ calories, proteinG, carbsG, fatG }` for 100 grams, copied from the lookup hit and not scaled to the portion |
| `foodId` | string | no | Id from the lookup hit |
| `source` | string | no | `catalog`, `usda`, `library`, or `web` |
| `ingredientFamily` | string | no | Family from the hit |
| `citationUrl` | string | no | Page the numbers came from, when there was no lookup hit |
| `entry_id` | string | no | Existing entry to update. Omit to create one. |
| `client_mutation_id` | string | no | Idempotency key |
| `confirmed` | boolean | no | Default `true`. A confirmed row counts in the day's totals. |

**Returns:** `{ "dayKey", "entryId" }`.

## `get_diary`

Read one day's entries and remaining macros. Use this before an edit, a delete, or a suggestion when you do not already have the rows.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `day_key` | string | yes | Diary day, `YYYY-MM-DD` |

**Returns:** `{ "dayKey", "entries", "remaining" }`. Each entry has `entryId`, `itemIndex`, `name`, `grams`, `mealSlot`, `foodId`, `source`, `per100g`, `ingredientFamily`. This is the diary, not the saved library.

## `search_catalog`

Look up a generic food in the seed catalog. Does not log. Hits stay in seed order. Pass the chosen hit's measures to `portion_to_grams`.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | string | yes | Food name, such as rice, egg, or paneer |
| `limit` | integer | no | Maximum hits. Default `10`. |

**Returns:** `{ "source": "catalog", "hits": [ … ] }`.

## `search_usda`

Fetch foods from USDA FoodData Central. Does not log. Hits stay in FoodData Central order.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | string | yes | Food name |
| `limit` | integer | no | Maximum hits. Default `8`. |

**Returns:** `{ "source": "usda", "hits": [ … ] }`.

## `search_library`

Match a name against the signed-in user's saved library. The server loads the rows. Does not log. A single generic word does not match a longer saved title. Listing or editing the library is `list_library`, `upsert_library_item`, and `delete_library_item`.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | string | yes | Saved food, recipe, or meal title |
| `limit` | integer | no | Maximum hits. Default `3`. |

**Returns:** `{ "source": "library", "hits": [ … ] }`.

## `lookup_barcode`

Look up one package barcode on Open Food Facts. A miss is `{ "found": false }`. Does not log.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `gtin` | string | yes | Barcode digits |

## `portion_to_grams`

Turn a quantity and unit into grams using the chosen hit's measures. An unknown unit returns `{ "unmapped": true }`.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `quantity` | number | yes | How many of the unit |
| `unit` | string | yes | Unit the user said, such as cup, large, or g |
| `measures` | array | no | Household measures from the hit. Pass them through unchanged. |

**Returns:** `{ "grams", "label" }` or `{ "unmapped": true }`.

## `delete_food_entry`

Delete one diary entry. Call this when the user wants that one entry gone. To change it, call `write_food_entry` with `entry_id` and the new fields. The iPhone callable for the same delete is `delete_meal`.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `day_key` | string | yes | Diary day, `YYYY-MM-DD` |
| `entry_id` | string | yes | Entry to delete |
| `client_mutation_id` | string | no | Idempotency key |

**Returns:** `{ "dayKey", "entryId" }`.

## `patch_profile`

Merge durable settings. Send only the keys that changed. Allowed keys: `timezone`, `dailyTarget`, `mealPlan`, `likes`, `dislikes`, `allergies`, `diets`, `assistanceLevel`, `responseStyle`, `longTermMemory`. Other keys are ignored. Do not use this to log a meal or edit the library.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `patch` | object | yes | Partial profile. Only the allowed keys are kept. |

**Returns:** `{ "profile": { ... } }`.

## `upsert_library_item`

Create or replace one saved library food, recipe, or meal. Call `list_library` first when you need an existing id to replace. This is not today's diary. Something they just ate is a lookup, `portion_to_grams`, then `write_food_entry`.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `item` | object | yes | Library row: `name`, `kind` (`food`, `recipe`, or `meal`). Include `id` to replace, plus macros and ingredients when you have them. |
| `client_mutation_id` | string | no | Idempotency key |

**Returns:** `{ "id" }`.

## `delete_library_item`

Soft-delete one library item. The row stays, marked deleted. Take `id` from `list_library` or from the upsert that created it. Do not use this to remove a diary entry; call `delete_food_entry`.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | yes | Library item id |
| `client_mutation_id` | string | no | Idempotency key |

**Returns:** `{ "id" }`.

## `list_library`

List saved library items. Use this before `upsert_library_item` or `delete_library_item` when you need ids or names. What they ate today is `get_diary`, not this list. Leave `include_deleted` false unless they asked for removed items.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `include_deleted` | boolean | no | Include soft-deleted rows. Default `false`. |

**Returns:** `{ "items": [ … ] }`.

## Not on this server

| Name | Where it lives |
|------|----------------|
| `interpret_meal` | Firebase callable for the iPhone. It runs Capy's model. Contract: [api-contracts.md](api-contracts.md). |
| `get_thread`, `patch_thread` | Firebase callables for the iPhone. Contract: [user-store.md](user-store.md#get_thread-contract). |
| `exchange_access_token` | Callable and `POST /exchange_access_token`. Contract: [api-contracts.md](api-contracts.md). |
| In-app confirm gate | The iPhone `interpret_meal` callable stages the first `write_food_entry` or `delete_food_entry`. The MCP tools of those names write immediately. List: [harness.md](harness.md). |
