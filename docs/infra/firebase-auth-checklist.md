# Firebase Auth checklist (Apple + Google)

Complete against GCP/Firebase project id recorded in `.firebaserc`.

## 1. Add Firebase to GCP project

If the project is GCP-only:

```bash
npx -y firebase-tools@latest projects:addfirebase <PROJECT_ID>
npx -y firebase-tools@latest use <PROJECT_ID>
```

## 2. Register iOS app

```bash
npx -y firebase-tools@latest apps:create IOS --bundle-id sagar.capy --display-name "Capy"
npx -y firebase-tools@latest apps:sdkconfig IOS <APP_ID>
```

Save as `capy/GoogleService-Info.plist` (gitignored).

## 3. Sign in with Apple

**Deferred** for now (product decision). Re-open when ready:

Apple Developer:

- [ ] App ID with Sign in with Apple capability
- [ ] Services ID / return URLs as required by Firebase docs for iOS native
- [ ] Team ID, Key ID, private key (.p8) configured in Firebase Console → Authentication → Sign-in method → Apple

Firebase:

- [ ] Enable Apple provider
- [ ] Paste Apple credentials

iOS app:

- [ ] Sign in with Apple capability on target
- [ ] Entitlements file

## 4. Google Sign-In

- [x] Google provider enabled in Firebase Console (`capy-dogfood`)
- [x] `GoogleService-Info.plist` installed at `capy/GoogleService-Info.plist` (gitignored)
- [x] Phase 2 Auth UI: Firebase `OAuthProvider(providerID: "google.com")` (native GoogleSignIn SPM deferred — version conflict with Firebase 13)
- [x] URL scheme / GIDClientID present in `AppInfo.plist` for future native GoogleSignIn SDK

## 5. Authorized domains

- [ ] `localhost` for emulator web tooling if needed
- [ ] Default Firebase domains present

## 6. Verify

- [ ] Emulator: create test users OR use real providers against staging
- [ ] Callable rejects missing token
