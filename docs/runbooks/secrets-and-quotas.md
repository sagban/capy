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
3. Model: `gemini-2.0-flash-001` (override with env `VERTEX_GEMINI_MODEL`)

Do **not** put an AI Studio `GEMINI_API_KEY` in the function for prod. Local emulator uses Vertex if ADC is available (`gcloud auth application-default login`); otherwise heuristics run.

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

1. Prefer Foundation + SR Legacy; reject incomplete nutrient records
2. Cache hits in-process; miss cache for the calendar day
3. Seed catalog covers top foods; USDA is fallback only

## Quotas (dogfood)

| Service | Dogfood expectation |
|---------|---------------------|
| Vertex Gemini | Low QPS; one interpret call per user utterance |
| USDA | Rare (seed covers top foods); watch daily free tier |
| Functions | Gen2 min instances = 0 for cost |

## App Check

Documented; **not enforced** until Phase 3.
