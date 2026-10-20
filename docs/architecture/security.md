# Security

## Secrets

| Secret | Where | Never |
|--------|-------|-------|
| Gemini / Vertex credentials | GCP Secret Manager → Functions | iOS binary, git |
| USDA FoodData Central API key | Secret Manager → Functions | iOS binary, git |
| `GoogleService-Info.plist` | Local + CI secrets; gitignored | Public forks with prod keys if rotated |

Local pattern: `.env` (gitignored) for emulator; see [../runbooks/local-dev.md](../runbooks/local-dev.md).

## Auth

- Firebase Auth: **Google Sign-In** + **email/password** (Sign in with Apple deferred). Password policy is Firebase's default (min 6 chars)
- Callable Functions validate Firebase ID token **or** short-lived Cappy access JWT (`exchange_access_token`; see [external-auth.md](external-auth.md))
- No anonymous auth for V1 dogfood API (Sign in required)
- `API_ACCESS_TOKEN_SECRET` (Secret Manager) signs access tokens for MCP/HTTP clients

## App Check

- **Phase 0 decision:** document and prepare; **do not enforce** until Phase 3 dogfood stabilizes
- Plan: DeviceCheck (iOS) when enforcing

## Client

- No Gemini/USDA keys in the app
- Treat `GoogleService-Info.plist` as non-secret-ish Firebase config but keep out of public samples when possible; rotate OAuth clients if leaked

## App Store privacy (draft)

Collect: account identifiers (Firebase uid), email (from Apple/Google as provided), food log content (on-device; server sees utterances for interpretation). Camera is used on-device for barcode scanning only; scanned GTINs are sent to the authenticated `lookup_barcode` callable (Open Food Facts). Photos are not stored.

Do not collect: HealthKit (until FR-10), precise location, contacts, photo library.

Nutrition is not medical advice; Cappy abstains from medical/ED/pregnancy coaching (product copy boundary).
