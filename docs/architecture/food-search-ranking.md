# Food search ranking (moat)

Goal: **correct food for logging with minimal friction** — not “a hit.” Wrong confirm is worse than abstain → clarify (or main-model web context, not harness web I/O).

## What the field does

| Domain | Pattern | Takeaway for Capy |
|--------|---------|-------------------|
| Classic IR | BM25 / BM25F (fielded title, brand, body) | Score **query↔name** and **query↔brand** separately; don’t treat FDC description blob as one bag |
| E‑commerce LTR ([Flipkart](https://arxiv.org/abs/1907.01549), [Walmart](https://arxiv.org/abs/2412.04637)) | Retrieve with BM25 → re-rank with query / item / query–item / context features; **broad vs narrow** queries | Broad (“rice”) → staples + trust; narrow (“ON whey”) → identity match or abstain |
| Nutrition apps (Cronometer, MFP) | Filter by Common / Brands / Restaurants; recents & favorites; barcode for labels | Personalization (today, likes, corrections) is first-class; brand nicknames need resolution, not forced generics |
| USDA FDC | Opaque relevance; Branded vs Foundation/SR; brandOwner is a separate field | Always **merge pools**, then rank ourselves; surface `brandOwner` in the label for fielded match |
| Safety | Barcode/search false positives (FDC docs) | **No confident result** beats wrong product |

We are **not** training LTR yet (no click/log labels). We use an explicit, testable feature score + confidence gate that mirrors those feature families.

## Feature families (v1)

1. **Query features** — breadth (`broad` \| `narrow`), token counts, identity tokens (short/ALLCAPS)
2. **Item features** — source (`seed` / `usda` / `usda_branded`), noise flags, nutrient completeness
3. **Query–item** — fielded lexical match (description vs brand), coverage, unexplained tokens, BM25-lite
4. **Context** — likes, today log, recent corrections, workingMemory / pending candidates

## Confidence policy

| Confidence | `results` | `suggestWebSearch` | When |
|------------|-----------|--------------------|------|
| `high` | Top ranked | false | Strong match, no unexplained identity tokens, clear gap |
| `medium` | Top ranked | sometimes | Usable but ambiguous — agent may clarify or web |
| `low` / `none` | **Empty** (hints only) | true | Unresolved tokens, weak match, empty pool |

## Code

- Ranker: `functions/food_search.py`
- USDA pool (unranked fetch): `functions/usda.py` → `search_usda_pool`
- Evals: `functions/tests/test_food_search_evals.py` + `fixtures/food_search_evals.json`

## Next (not v1)

- Offline LTR once we have confirm/reject labels from chat
- Embedding similarity for vocabulary gap (restaurant slang ↔ catalog)
- Barcode path (exact GTIN only)
