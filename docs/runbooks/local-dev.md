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

Copy examples and fill locally (never commit):

```bash
cp .env.example .env
cp functions/.env.example functions/.env   # if present
```

Required for harness later:

- `GEMINI_API_KEY` or Vertex ADC
- `USDA_API_KEY` (data.gov)

Production uses Secret Manager — see [secrets-and-quotas.md](secrets-and-quotas.md).

## Emulators

```bash
npx -y firebase-tools@latest emulators:start --only auth,functions
```

| Service | Default host |
|---------|----------------|
| Auth | `127.0.0.1:9099` |
| Functions | `127.0.0.1:5001` |
| UI | `127.0.0.1:4000` |

Point the iOS `AgentClient` at the Functions emulator in DEBUG builds.

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
