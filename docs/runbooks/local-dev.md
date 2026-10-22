# Local development runbook

## Prerequisites

- Xcode 16+ / iOS Simulator
- Node 20+ (for Firebase CLI via `npx`)
- Python 3.12+ (Functions)
- Firebase CLI: `npx -y firebase-tools@latest`
- Logged in: `npx -y firebase-tools@latest login`

## Project binding

1. Set active project (replace with your GCP/Firebase project id):

```bash
npx -y firebase-tools@latest use <PROJECT_ID>
```

2. Confirm `.firebaserc` contains the project alias `default`.

3. Fetch iOS config (after iOS app is registered):

```bash
npx -y firebase-tools@latest apps:sdkconfig IOS <APP_ID> > /tmp/GoogleService-Info.plist
# Copy into capy/ (gitignored). Link in Xcode target.
```

## Secrets (local)

```bash
# Optional project ids for tooling
cp .env.example .env

# Emulator-only Vertex model / location (do NOT set GOOGLE_CLOUD_PROJECT — reserved)
cp functions/.env.example functions/.env

# Emulator override for USDA SecretParam (optional; seed catalog works without a real key)
# printf 'USDA_FDC_API_KEY=your-data-gov-key\n' > functions/.secret.local
```

Gemini in prod/emulator: **Vertex ADC** (`~/.config/gcloud/application_default_credentials.json`).  
USDA in prod: Secret Manager — see [secrets-and-quotas.md](secrets-and-quotas.md).

## Emulators

```bash
./run.sh
```

(`run.sh` ensures `functions/venv`, seeds `.env` / `.secret.local` if missing, starts **Phoenix** on `:6006` when `CAPY_PHOENIX=1`, then Auth + Functions.)

| Service | Host |
|---------|------|
| Phoenix traces | http://127.0.0.1:6006 (`capy-harness`) |
| Auth | `127.0.0.1:9099` |
| Functions | `127.0.0.1:5001` |
| Emulator UI | http://127.0.0.1:4000 |

Disable Phoenix: set `CAPY_PHOENIX=0` in `functions/.env`.

Manual equivalent:

```bash
cd functions && python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd ..
npx -y firebase-tools@latest emulators:start --only auth,functions
```

| Service | Default host |
|---------|----------------|
| Auth | `127.0.0.1:9099` |
| Functions | `127.0.0.1:5001` |
| Emulator UI | `127.0.0.1:4000` |
| Phoenix | `127.0.0.1:6006` |

The **capy Local** scheme sets `CAPY_ENVIRONMENT=local`; `AppEnvironment.local` routes `AgentClient` to the Functions emulator.

### Harness unit / golden tests (no emulator required)

```bash
cd functions
source .venv/bin/activate
pytest tests/test_harness_goldens.py -q
```

Goldens cover: clarify follow-up via workingMemory, long-thread window, today-log tool, vegetarian propose filter, long-term memory add/forget, no trusted macros in responses.

## Deploy Functions (dogfood)

Firebase Python Functions expect a local `functions/venv` (CLI discovery), even though `venv` is not uploaded.

```bash
cd functions
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
npx -y firebase-tools@latest deploy --only functions --project capy-dogfood
```

Callable: `interpret_meal` in `us-central1` (codebase `capy-harness`).

Production Gemini = **Vertex AI + ADC** (GCP credits). USDA = Secret Manager `USDA_FDC_API_KEY`. See [secrets-and-quotas.md](secrets-and-quotas.md).

iOS **capy Prod** calls deployed `interpret_meal` via Firebase Functions SDK. **capy Local** uses `AppEnvironment.local.baseURL` (Functions emulator).

## iOS schemes (Local vs Prod)

| Scheme | Build configs | Harness |
|--------|---------------|---------|
| **capy Local** | `DebugLocal` / `ReleaseLocal` → [`Config/Local.xcconfig`](../../Config/Local.xcconfig) | Functions emulator `127.0.0.1:5001`. MCP config points at `service_app` on port 8080. |
| **capy Prod** | `DebugProd` / `ReleaseProd` → [`Config/Prod.xcconfig`](../../Config/Prod.xcconfig) | Deployed `interpret_meal` on `capy-dogfood`. MCP config points at Cloud Run `cappy-api`. |

`AppEnvironment` owns per-env behavior; `EnvironmentConfig` resolves the active scheme (`CAPY_LOCAL` / `CAPYEnvironment`). Pick the scheme in Xcode before Run.

Local run checklist:

1. `./run.sh` (also writes `Config/LocalEmulatorHost.xcconfig` with your Mac LAN IP)
2. Xcode scheme → **capy Local** → rebuild
3. Sign in (production Auth is fine; Functions hit the emulator)
4. **Simulator** uses `127.0.0.1`. **Physical device** uses the LAN IP from step 1 — rebuild after `./run.sh` so the IP is baked in.

Prod dogfood: scheme → **capy Prod** (no emulator).

## iOS

1. Open `capy.xcodeproj`
2. Choose **capy Local** or **capy Prod**
3. Ensure bundle id matches Firebase iOS app (`sagar.capy`)
4. `FirebaseApp.configure()` in `App.init()` before Auth state objects

## Auth providers checklist

See [../infra/firebase-auth-checklist.md](../infra/firebase-auth-checklist.md).

## CI (decision)

- **Phase 0:** optional GitHub Actions for Python lint/test later
- Xcode Cloud deferred
