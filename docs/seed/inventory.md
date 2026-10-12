# Food catalog (USDA + overlay)

## How the catalog is built

Not a hand-curated demo list. Production catalog is generated from USDA FoodData Central downloads:

```bash
python3 scripts/build_food_catalog.py
```

| Source | Contents |
|--------|----------|
| USDA Foundation Foods | Analytical reference foods |
| USDA SR Legacy | Broad classic nutrient database |
| [`CatalogOverlay.json`](../../capy/Resources/CatalogOverlay.json) | Indian/custom foods + composites (paneer, roti, dal, …) |

Outputs:

- [`capy/Resources/SeedFoods.json`](../../capy/Resources/SeedFoods.json) (~8k foods, ~1.7 MB)
- [`functions/seed/SeedFoods.json`](../../functions/seed/SeedFoods.json) (same file for harness)

Raw USDA zips live under `scripts/data/usda/` (gitignored). Re-run the script when USDA releases updates.

## On device

`SeedImporter` upserts `SeedFoods.json` into SwiftData on launch (catalog `version` bump forces refresh). Manual Log searches this catalog.

## Online fallback

Functions `search_food` still calls the USDA API when the bundled catalog misses (branded / obscure items).

## Overlay foods

Keep only items USDA covers poorly (regional staples). Composites may `resolve:<exact USDA description>` so the build script binds stable `usda_*` ids.
