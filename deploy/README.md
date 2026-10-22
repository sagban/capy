# Cloud Run deploy (health + auth exchange + MCP)

Single service **`cappy-api`** runs `functions/service_app.py`:

- `GET /healthz`
- `POST /exchange_access_token`
- MCP Streamable HTTP at `POST /mcp/` (spec 2025-11-25)

Meal APIs are **not** on Cloud Run HTTP — use Firebase **callables** (iOS) or **MCP tools** on this service (Alexa, agents).

```bash
# From repo root
docker build -t gcr.io/capy-dogfood/cappy-api:latest functions
docker push gcr.io/capy-dogfood/cappy-api:latest

gcloud run services replace deploy/cloudrun-service.yaml \
  --region us-central1 \
  --project capy-dogfood

# Secrets (example)
gcloud run services update cappy-api \
  --region us-central1 \
  --project capy-dogfood \
  --set-secrets=API_ACCESS_TOKEN_SECRET=API_ACCESS_TOKEN_SECRET:latest,USDA_FDC_API_KEY=USDA_FDC_API_KEY:latest
```

MCP URL: `{service-url}/mcp/` — see [alexa-setup.md](../docs/architecture/alexa-setup.md).

Firebase **callables** (`functions/main.py`) remain `firebase deploy --only functions` for the iOS app.
