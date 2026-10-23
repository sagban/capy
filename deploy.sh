#!/usr/bin/env bash
# Deploy Firebase callables and the Cloud Run MCP service (capy-mcp).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

"$ROOT/configure.sh"
set -a
# shellcheck disable=SC1091
source "$ROOT/capy.env"
set +a
PROJECT="$CAPY_GCP_PROJECT"
REGION="$CAPY_REGION"
SERVICE="$CAPY_MCP_SERVICE"
IMAGE="gcr.io/${PROJECT}/${SERVICE}:latest"
VENV="$ROOT/functions/venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating functions/venv (python3.12)…"
  python3.12 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q -r "$ROOT/functions/requirements.txt"

echo "Deploying Firebase functions…"
npx -y firebase-tools@latest deploy --only functions --project "$PROJECT"

echo "Building ${IMAGE} with Cloud Build…"
gcloud builds submit "$ROOT/functions" --project "$PROJECT" --tag "$IMAGE"

echo "Replacing Cloud Run service ${SERVICE}…"
RENDERED="$(mktemp)"
sed \
  -e "s|__CAPY_GCP_PROJECT__|${PROJECT}|g" \
  -e "s|__CAPY_SERVICE__|${SERVICE}|g" \
  -e "s|__FIRESTORE_DATABASE_ID__|${FIRESTORE_DATABASE_ID}|g" \
  -e "s|__VERTEX_LOCATION__|${GOOGLE_CLOUD_LOCATION}|g" \
  -e "s|__VERTEX_MODEL__|${VERTEX_GEMINI_MODEL}|g" \
  deploy/cloudrun-service.yaml > "$RENDERED"
gcloud run services replace "$RENDERED" --region "$REGION" --project "$PROJECT"
rm -f "$RENDERED"

# /authenticate calls Identity Toolkit. Pass FIREBASE_WEB_API_KEY from your Firebase web app.
if [[ -n "${FIREBASE_WEB_API_KEY:-}" ]]; then
  gcloud run services update "$SERVICE" \
    --region "$REGION" --project "$PROJECT" \
    --update-env-vars "FIREBASE_WEB_API_KEY=${FIREBASE_WEB_API_KEY}"
else
  echo "FIREBASE_WEB_API_KEY is unset. /authenticate cannot sign in until you set it on ${SERVICE}."
fi

gcloud run services add-iam-policy-binding "$SERVICE" \
  --region "$REGION" --project "$PROJECT" \
  --member="allUsers" --role="roles/run.invoker" \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format='value(status.url)')"
"$ROOT/configure.sh" --set "CAPY_MCP_URL=${URL}/mcp/"
echo "MCP: ${URL}/mcp/"
echo "Sign in: ${URL}/authenticate"
echo "Wrote that MCP URL into capy.env and app/Config/Secrets.xcconfig"
