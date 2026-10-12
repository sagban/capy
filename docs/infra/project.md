# GCP / Firebase project

## Active dogfood project

| Item | Value |
|------|-------|
| Project ID | `capy-dogfood` |
| Display name | Capy |
| Console | https://console.firebase.google.com/project/capy-dogfood/overview |
| iOS App ID | `1:322403791923:ios:1aec38036bfb4c02e1df46` |
| Bundle ID | `sagar.capy` |
| CLI account | `sagarbansal099@gmail.com` |
| Billing | Not enabled yet (enable before Vertex/heavy Functions) |

`.firebaserc` points `default` → `capy-dogfood`.

`GoogleService-Info.plist` is downloaded under `capy/` and **gitignored**. Regenerate with:

```bash
npx -y firebase-tools@latest apps:sdkconfig IOS 1:322403791923:ios:1aec38036bfb4c02e1df46 -o capy/GoogleService-Info.plist
```

## Note on owner’s prior GCP project

A GCP project reported as “capy” was **not** accessible to this Firebase login (`PERMISSION_DENIED` on `addFirebase`). Phase 0 therefore provisioned **`capy-dogfood`** for dogfood.

To switch later:

1. Ensure `sagarbansal099@gmail.com` (or re-login) owns the other project
2. `npx -y firebase-tools@latest projects:addfirebase <PROJECT_ID>`
3. Update `.firebaserc` and re-register / re-download iOS config

## Auth providers

| Provider | Status |
|----------|--------|
| Google Sign-In | Enable in [Console → Authentication](https://console.firebase.google.com/project/capy-dogfood/authentication/providers) (CLI auth deploy hit OAuth duplicate errors) |
| Sign in with Apple | Requires Apple Developer key + Firebase Console / Services ID — see [firebase-auth-checklist.md](firebase-auth-checklist.md) |

## Next infra (still manual / Phase 1)

- [ ] Enable billing if using Vertex AI
- [ ] Create Secret Manager secrets `GEMINI_API_KEY` / `USDA_FDC_API_KEY`
- [ ] Complete Apple Sign In credentials in Console
- [ ] Deploy Functions scaffold when ready
