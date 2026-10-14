# Firebase Auth checklist (Apple + Google + email)

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
- [x] Phase 2 Auth UI: native `GoogleSignIn` SDK + `GoogleAuthProvider` (Firebase pinned to 12.x for package compatibility)
- [x] URL scheme / GIDClientID present in `AppInfo.plist`

## 5. Email / password

- [x] Email/Password provider enabled in Firebase Console (`capy-dogfood`)
- [x] Auth UI: `Auth.auth().signIn(withEmail:)`, `createUser(withEmail:)`, `sendPasswordReset(withEmail:)` in `AuthManager`
- No email verification gate in V1 dogfood

## 6. Authorized domains

- [ ] `localhost` for emulator web tooling if needed
- [ ] Default Firebase domains present

## 7. Verify

- [ ] Emulator: create test users OR use real providers against staging
- [ ] Callable rejects missing token
