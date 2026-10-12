# Secret Manager, Vertex/Gemini, USDA

## Region / hosting

| Item | V1 choice |
|------|-----------|
| Functions region | `us-central1` (adjust if user prefers) |
| Runtime | Python 3.12, 2nd gen |
| Orchestration | LangGraph inside Functions |

## Secrets (names)

| Secret id | Used by |
|-----------|---------|
| `GEMINI_API_KEY` | LangGraph interpret node (or use Vertex ADC instead) |
| `USDA_FDC_API_KEY` | `search_food` USDA fallback |

Grant the Functions runtime service account `secretmanager.secretAccessor` on these secrets.

## Vertex / Gemini

Preferred with Firebase/GCP: enable **Vertex AI API** on the same project and call Gemini via Vertex (ADC) so no long-lived API key in env if possible.

Fallback: Gemini Developer API key in Secret Manager.

## USDA

1. Create a key at [api.data.gov](https://api.data.gov/)
2. Store as `USDA_FDC_API_KEY`
3. Prefer Foundation + SR Legacy; reject incomplete nutrient records
4. Cache hits permanently; cache misses for the calendar day

## Quotas (dogfood)

| Service | Dogfood expectation |
|---------|---------------------|
| Gemini | Low QPS; one interpret call per user utterance |
| USDA | Rare (seed covers top foods); watch daily free tier |
| Functions | Gen2 min instances = 0 for cost |

## App Check

Documented; **not enforced** until Phase 3.
