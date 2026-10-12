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

# Emulator-only USDA key (prod uses Secret Manager — not this file)
cp functions/.env.example functions/.env
# Edit functions/.env → USDA_FDC_API_KEY=<data.gov key>
```

Gemini in prod/emulator: **Vertex ADC** (no API key file).  
USDA in prod: Secret Manager — see [secrets-and-quotas.md](secrets-and-quotas.md).

## Emulators

```bash
cd functions && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..
npx -y firebase-tools@latest emulators:start --only auth,functions
```

| Service | Default host |
|---------|----------------|
| Auth | `127.0.0.1:9099` |
| Functions | `127.0.0.1:5001` |
| UI | `127.0.0.1:4000` |

Point the iOS `AgentClient` at the Functions emulator in DEBUG builds by setting env `CAPY_USE_FUNCTIONS_EMULATOR=1`.

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

iOS production builds call `https://us-central1-capy-dogfood.cloudfunctions.net/interpret_meal`. DEBUG + `CAPY_USE_FUNCTIONS_EMULATOR=1` uses the emulator instead.

## iOS

1. Open `capy.xcodeproj`
2. Ensure bundle id matches Firebase iOS app (`sagar.capy` unless changed)
3. Add Firebase iOS SDK via SPM when implementing Auth (Phase 2)
4. `FirebaseApp.configure()` in `App.init()` before Auth state objects

## Auth providers checklist

See [../infra/firebase-auth-checklist.md](../infra/firebase-auth-checklist.md).

## CI (decision)

- **Phase 0:** optional GitHub Actions for Python lint/test later
- Xcode Cloud deferred
