# Secret Manager, Vertex/Gemini, USDA

## Region / hosting

| Item | V1 choice |
|------|-----------|
| Project | `capy-dogfood` |
| Functions region | `us-central1` |
| Runtime | Python 3.12, 2nd gen |
| Orchestration | LangGraph inside Functions |
| Gemini | **Vertex AI** via ADC (GCP billing / credits) |

## Gemini (Vertex — no API key)

Production path uses Vertex AI on the same project. Cloud Functions Application Default Credentials call Gemini; usage bills the linked Cloud Billing account (your GCP credits apply).

1. Enable **Vertex AI API** on `capy-dogfood`
2. Grant the Functions runtime service account **Vertex AI User** (`roles/aiplatform.user`)
   - Default compute SA: `PROJECT_NUMBER-compute@developer.gserviceaccount.com`
3. Model: `gemini-3.5-flash` at Vertex location `global` (override with `VERTEX_GEMINI_MODEL` / `GOOGLE_CLOUD_LOCATION`)
4. Enable Google Search grounding on the main meal-agent model turn (Vertex `GoogleSearch` in `generate_with_tools`; needs Gemini 3+)

Do **not** put an AI Studio `GEMINI_API_KEY` in the function for prod. Local emulator uses Vertex if ADC is available (`gcloud auth application-default login`). Unit tests set `CAPY_MOCK_AGENT=1` (no live Vertex). Live path **fails closed** if Vertex is unavailable — no keyword intent fallback.

## Secrets (Secret Manager)

| Secret id | Used by | Required |
|-----------|---------|----------|
| `USDA_FDC_API_KEY` | `search_food` USDA fallback | Yes (bound on `interpret_meal`) |

Gemini does **not** use Secret Manager — Vertex uses ADC.

### Create / rotate USDA secret

```bash
# Interactive
npx -y firebase-tools@latest functions:secrets:set USDA_FDC_API_KEY --project capy-dogfood

# Or non-interactive from a local file (never commit the file)
printf '%s' "$USDA_FDC_API_KEY" | npx -y firebase-tools@latest functions:secrets:set USDA_FDC_API_KEY --project capy-dogfood --data-file=-
```

Get a key at [api.data.gov](https://api.data.gov/). Firebase binds the secret into the function env as `USDA_FDC_API_KEY` and grants the runtime SA `secretmanager.secretAccessor`.

### Redeploy after secret changes

```bash
cd functions && source venv/bin/activate   # or: python3.12 -m venv venv && pip install -r requirements.txt
cd ..
npx -y firebase-tools@latest deploy --only functions --project capy-dogfood
```

## USDA behavior

1. The model calls `search_catalog`, `search_usda`, or `search_library` on its own. `search_items` / `compose_suggestions` resolve drafts through the seed catalog only, then drop diet conflicts. USDA is not merged into that path.
2. Incomplete nutrient records dropped; same-day miss cache when the pool is empty
3. Low confidence / unresolved query tokens → `suggestWebSearch` (resolve via web, then search again)

## Quotas (dogfood)

| Service | Dogfood expectation |
|---------|---------------------|
| Vertex Gemini | Low QPS; one interpret call per user utterance |
| USDA | Rare (seed covers top foods); watch daily free tier |
| Functions | Gen2 min instances = 0 for cost |

## App Check

Documented; **not enforced** until Phase 3.
