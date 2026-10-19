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

- `scripts/migrate_composites_to_recipes.py` — one-off: copy existing `foodCorpus` `dataType==composite` → `recipes` (leaves old corpus rows for rollback).
- `scripts/import_seed_food_corpus.py` — writes foods/templates to `foodCorpus` and composites to `recipes`.

## Follow-up (not done here)

- `catalog.search_seed`: optionally search `recipes` by name (separate from staple foods).
- iOS: `LibraryEditorSheet` ingredient list; `SeedImporter` stop rolling composite macros into a single `Food` per 100g.
- Delete legacy composite docs from `foodCorpus` after clients read `recipes`.
