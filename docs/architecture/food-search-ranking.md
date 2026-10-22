# Food search

Each source is its own Gemini tool. The agent does not merge them into one ranked list.

| Tool | Lookup | Order |
|------|--------|--------|
| `search_catalog` | `functions/agent/tools/search/catalog.py` (`search_seed`) | Seed match order |
| `search_usda` | `functions/agent/tools/search/usda.py` (`search_usda_pool`) | FoodData Central order |
| `search_library` | `functions/agent/tools/search/library_match.py` | Strict title match |
| `lookup_barcode` | `functions/agent/tools/search/open_food_facts.py` | Exact GTIN, or `{ "found": false }` |

The shared tools in `functions/agent/tools/` call those lookups and return that source's hits. They do not log. Inside `interpret_meal`, a diet or allergy conflict is marked on the hit and the hit stays in the list. A cited menu is passed on `write_food_entry` as `per100g` plus `citationUrl`. The caller does not search that line.

The barcode scanner uses the same Open Food Facts lookup through the `lookup_barcode` callable.

## Offline ranker

`functions/agent/tools/search/food_search.py` (`rank_candidates`, `confidence_for`, `query_breadth`) scores a pool the caller already fetched. Evals: `functions/tests/test_food_search_evals.py` and `fixtures/food_search_evals.json`. The agent does not call it.

| Confidence | Results | When |
|------------|---------|------|
| `high` | Top hit | Strong match, no unexplained tokens, clear gap |
| `medium` | Top hit | Usable, possibly ambiguous |
| `low` / `none` | Empty | Weak match, unresolved tokens, or an empty pool |

Features: query breadth (`broad` or `narrow`), item source and completeness, fielded name/brand match, and context (likes, today's log, corrections, working memory).
