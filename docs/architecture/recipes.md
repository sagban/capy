# Recipes (Firestore)

Multi-ingredient dishes are stored outside `foodCorpus`.

## Collection: `recipes` (database `capy`)

| Document | Purpose |
|----------|---------|
| `recipes/{recipeId}` | Named recipe / seed composite |
| `recipes/_meta/catalog/current` | Import/migration metadata (`recipeCount`, `fileHash`, …) |

### `recipes/{recipeId}` fields

| Field | Type | Notes |
|-------|------|--------|
| `recipeId` | string | Same as doc id (`seed_*` for bundled composites) |
| `name` | string | Display name |
| `notes` | string | Optional |
| `kind` | `"composite"` \| `"recipe"` | Seed overlay composites use `composite`; user recipes use `recipe` (future) |
| `ingredients` | `{ foodId, grams }[]` | References `foodCorpus` (or seed ids) |
| `source` | string | e.g. `seed` |
| `catalogVersion` | int | From `SeedFoods.json` version |
| `updatedAt` / `updatedAtEpoch` | string / number | |

`foodCorpus` holds **atomic** foods, FDC rows, and meal **templates** (`dataType: template`). Composites are **not** written to `foodCorpus` on new seed imports.

## Scripts

- `scripts/import_seed_food_corpus.py` — writes foods and templates to `foodCorpus`, and composites to `recipes`.

## iOS Library recipes & meals (local)

- **Recipes** — compose from catalog foods only (grams); macros summed from per-100g snapshots on `LibraryItem.ingredientsJSON`.
- **Meals** — same composer, but items may be catalog foods **or** library recipes / foods / other meals (counted in servings, macros snapped at add time).
- **Foods** — simple name + manual macros (no composition).
- Logging a library recipe or meal still logs **one serving** (summed macros) via Manual Log.
- User library (food / recipe / meal) syncs to Firestore `users/{uid}/library/{id}` via `upsert_library_item` / `delete_library_item` / `list_library`.

`search_seed` searches staple foods in the seed catalog. It does not query this `recipes` collection.
