# Alexa account linking & skill setup

How to link an Amazon Alexa skill to a Cappy user and call the meal-agent APIs with the same bearer tokens as [MCP / HTTP clients](external-auth.md).

## Project binding (dogfood)

| Item | Value | Where to confirm |
|------|--------|------------------|
| **GCP / Firebase project ID** | `capy-dogfood` | [docs/infra/project.md](../infra/project.md), `.firebaserc`, `capy/App/EnvironmentConfig.swift` |
| **Cloud Functions region** | `us-central1` | `functions/main.py` (`region="us-central1"`), `EnvironmentConfig.functionsRegion` |

Other environments use the same URL pattern with a different `{project}`.

---

## 1. Hosted endpoint URLs

### Callable base URL pattern (production)

Firebase **2nd gen** HTTPS callables deploy as named functions in the configured region:

```text
https://{region}-{project}.cloudfunctions.net/{functionName}
```

**Dogfood base:**

```text
https://us-central1-capy-dogfood.cloudfunctions.net
```

**HTTP wire format** (all callables below):

```http
POST https://us-central1-capy-dogfood.cloudfunctions.net/{functionName}
Authorization: Bearer <Firebase ID token | Cappy access JWT>
Content-Type: application/json

{"data": { ... } }
```

Response envelope: `{ "result": { ... } }` or `{ "error": { ... } }`.

Verify deployed names after deploy:

```bash
npx -y firebase-tools@latest functions:list --project capy-dogfood
```

### Callable function URLs (dogfood)

| Function | URL |
|----------|-----|
| `exchange_access_token` | `https://us-central1-capy-dogfood.cloudfunctions.net/exchange_access_token` |
| `interpret_meal` | `https://us-central1-capy-dogfood.cloudfunctions.net/interpret_meal` |
| `log_meal` | `https://us-central1-capy-dogfood.cloudfunctions.net/log_meal` |
| `patch_profile` | `https://us-central1-capy-dogfood.cloudfunctions.net/patch_profile` |
| `get_thread` | `https://us-central1-capy-dogfood.cloudfunctions.net/get_thread` |
| `patch_thread` | `https://us-central1-capy-dogfood.cloudfunctions.net/patch_thread` |

**Emulator** (local only):

```text
http://127.0.0.1:5001/capy-dogfood/us-central1/{functionName}
```

See [runbooks/local-dev.md](../runbooks/local-dev.md).

### Account linking OAuth URLs (Alexa console)

Alexa **Auth Code Grant** expects a browser **authorization URI** and an **access token URI**. Cappy’s meal APIs use **Cappy access JWTs** ([external-auth.md](external-auth.md)); Alexa’s token step must mint those JWTs (same as `exchange_access_token`), not raw Firebase ID tokens.

**Recommended hosting** (Firebase Hosting — add when you ship the linking UI):

| Purpose | URL (dogfood example) |
|---------|------------------------|
| Authorization page (login webview) | `https://capy-dogfood.web.app/alexa/authorize` |
| Access token URI (OAuth token endpoint) | `https://capy-dogfood.web.app/alexa/token` |

**Alternative** (dedicated HTTP Cloud Functions):

| Purpose | URL (dogfood example) |
|---------|------------------------|
| Authorization redirect handler | `https://us-central1-capy-dogfood.cloudfunctions.net/alexa_oauth_authorize` |
| Token endpoint | `https://us-central1-capy-dogfood.cloudfunctions.net/alexa_oauth_token` |

These OAuth routes are **not** in the repo yet; they are the contract Alexa linking should implement. Until they exist, you can test the skill with a manually obtained token (`exchange_access_token` + Firebase sign-in) — see checklist below.

### Cloud Run (`cappy-api`)

Dogfood runs one container (`functions/Dockerfile`, service **`cappy-api`**, [deploy/cloudrun-service.yaml](../../deploy/cloudrun-service.yaml)) with **only**:

- `GET /healthz`
- `POST /exchange_access_token` (mint Cappy access JWT from `firebaseIdToken`; body `{"data":…}` or bare JSON)
- **MCP Streamable HTTP** (spec 2025-11-25) at `/mcp/`

Meal APIs are **not** exposed as raw HTTP on Cloud Run. **iOS** uses Firebase **callables** (table above). **Alexa / MCP clients** use hosted MCP or callables — not duplicate HTTP routes on Run.

**Base URL pattern** (after deploy):

```text
https://{service}-{project-number}.{region}.run.app
```

Dogfood example (service `cappy-api`, region `us-central1`):

```text
https://cappy-api-XXXXXXXXXX.us-central1.run.app
```

Find the live URL:

```bash
gcloud run services describe cappy-api --region us-central1 --project capy-dogfood --format='value(status.url)'
```

| Route | Method | Auth |
|-------|--------|------|
| `/healthz` | GET | none |
| `/exchange_access_token` | POST | none (body: `firebaseIdToken`) |
| `/mcp/` | POST, GET | Bearer |

### MCP server (hosted)

| Endpoint | Purpose |
|----------|---------|
| `POST {base}/mcp/` | Streamable HTTP JSON-RPC (initialize, tools/list, tools/call) |
| `GET {base}/mcp/` | Optional server-to-client stream on the same endpoint |

**Hosted MCP URL:**

```text
https://cappy-api-XXXXXXXXXX.us-central1.run.app/mcp/
```

Send `Accept: application/json, text/event-stream` and `Content-Type: application/json`. A successful `initialize` returns `protocolVersion` `2025-11-25`. The trailing slash is required.

Every MCP HTTP request must include:

```http
Authorization: Bearer <Firebase ID token | Cappy access JWT>
```

Tools on the hosted server: `search_catalog`, `search_usda`, `search_library`, `lookup_barcode`, `portion_to_grams`, `get_diary`, `write_food_entry`, `delete_food_entry`, `patch_profile`, `upsert_library_item`, `delete_library_item`, `list_library`. `interpret_meal`, `get_thread`, and `patch_thread` stay Firebase callables for the iPhone. Implementation: `functions/agent/mcp_host.py`, mounted in `functions/service_app.py`.

**Alexa:** use account-linked **Bearer** token with hosted MCP (`{base}/mcp/`) from the skill backend, or call Firebase **callables** directly (see §4). Do not point Alexa account linking at MCP OAuth scopes; linking only supplies the access token your backend sends on MCP HTTP.

---

## 2. Alexa Developer Console — account linking

In the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) → your skill → **Build** → **Account Linking**.

| Console field | Dogfood example | Maps to Cappy |
|---------------|-----------------|---------------|
| **Authorization URI** | `https://capy-dogfood.web.app/alexa/authorize` | User sign-in page (Firebase Auth UI / custom page). Must accept Alexa query params (below). |
| **Access Token URI** | `https://capy-dogfood.web.app/alexa/token` | Server exchanges `authorization_code` for tokens; internally calls the same minting logic as `exchange_access_token` (`API_ACCESS_TOKEN_SECRET`). |
| **Client ID** | `cappy-alexa-dogfood` (you choose) | Must match the value your authorize + token endpoints expect. Store in Firebase / Secret Manager. |
| **Client Secret** | Generated secret (Alexa + Cappy server) | Store in Secret Manager (e.g. `ALEXA_OAUTH_CLIENT_SECRET`); validate on token POST. |
| **Authorization grant type** | Auth Code Grant | `response_type=code` on authorize; `grant_type=authorization_code` on token. |
| **Access token scheme** | HTTP Bearer | Same `Authorization: Bearer` as callables. |
| **Client authentication scheme** | HTTP Basic or credentials in body | Match your token endpoint implementation. |
| **Scopes** | Optional (e.g. `cappy:meal`) | Document only; Cappy JWT is uid-scoped. |
| **Domain list** | `capy-dogfood.web.app` (or your auth host) | Required for webview. |
| **Redirect URLs** | From Alexa console (copy) | Typically `https://alexa.amazon.com/spa/skill-account-linking/v1/authorize` (and variants). Your authorize page must redirect here with `?code=...&state=...`. |

Alexa opens the authorization URI with query parameters such as:

```text
?client_id=cappy-alexa-dogfood
&response_type=code
&state=<alexa-state>
&redirect_uri=https://alexa.amazon.com/spa/skill-account-linking/v1/authorize
&scope=...
```

Your token endpoint receives (typical auth-code exchange):

```http
POST /alexa/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=<one-time-code>
&redirect_uri=...
&client_id=cappy-alexa-dogfood
&client_secret=...
```

**Success response** (OAuth 2.0 shape Alexa expects):

```json
{
  "access_token": "<Cappy JWT>",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "<optional; implement if you need silent refresh>"
}
```

The `access_token` value must be a **Cappy access JWT** verifiable by `functions/agent/auth.py` (`iss=capy`, `aud=capy-api`). That is the same token type returned by:

```json
POST exchange_access_token
{"data": {"firebaseIdToken": "<Firebase ID token>"}}
→ { "accessToken", "expiresIn": 3600, "uid" }
```

---

## 3. Authorize page (Firebase Auth webview)

The page at **Authorization URI** is shown inside Alexa’s account-linking webview. It should:

1. **Parse** `client_id`, `redirect_uri`, `state`, `response_type` from the query string; reject unknown `client_id`.
2. **Sign the user in** with **Firebase Auth** (email/password and/or Google — same providers as iOS; see [firebase-auth-checklist.md](../infra/firebase-auth-checklist.md)):
   - [FirebaseUI](https://firebase.google.com/docs/auth/web/firebaseui) on a static Hosting page, or
   - `signInWithRedirect` / `signInWithPopup` with your web Firebase config (`apiKey`, `authDomain`, etc.).
3. **On successful Firebase sign-in**, obtain a Firebase **ID token** (`user.getIdToken()`).
4. **Create a one-time authorization code** (random, short TTL, store in Firestore e.g. `alexaOAuthCodes/{code}` with `uid`, `expiresAt`, `used: false`). Do **not** put the Firebase ID token in the redirect URL.
5. **Redirect** the browser to Alexa:

   ```text
   {redirect_uri}?code={one-time-code}&state={state}
   ```

6. **Errors**: redirect with `error=access_denied` (and `state`) per OAuth conventions, or show an inline error for invalid `client_id`.

The **token URI** (separate backend route) validates `code` + `client_id` + `client_secret`, marks the code used, and returns `access_token` = `mint_access_token(uid)` from the stored uid.

**Security:** HTTPS only; single-use codes; short expiry (e.g. 5 minutes); rate-limit token endpoint; keep `client_secret` only on server.

---

## 4. Alexa skill code sketch

Alexa passes the linked **access token** on each request (`event.context.System.user.accessToken` in the JSON request to your Lambda).

### Option A — Firebase callables (simplest Lambda integration)

Node.js Lambda (axios), after account linking:

```javascript
const REGION = "us-central1";
const PROJECT = "capy-dogfood";
const BASE = `https://${REGION}-${PROJECT}.cloudfunctions.net`;

async function callCappy(name, accessToken, data) {
  const res = await fetch(`${BASE}/${name}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ data }),
  });
  const envelope = await res.json();
  if (envelope.error) throw new Error(JSON.stringify(envelope.error));
  return envelope.result;
}

// In your intent handler (user already linked):
const token = handlerInput.requestEnvelope.context.System.user.accessToken;
if (!token) {
  return handlerInput.responseBuilder
    .speak("Link Cappy in the Alexa app to log meals.")
    .withLinkAccountCard()
    .getResponse();
}

const today = new Date().toISOString().slice(0, 10); // or user timezone from profile
const result = await callCappy("interpret_meal", token, {
  utterance: "I had eggs and toast",
  dayKey: today,
  timezone: "America/Chicago",
  useServerContext: true,
});

const reply = result.assistantMessage || "Done.";
return handlerInput.responseBuilder.speak(reply).getResponse();
```

Other intents can call `log_meal`, `get_thread` (`limit`, `cursor`), etc. — see [api-contracts.md](api-contracts.md) and [mcp-tools.md](mcp-tools.md).

### Option B — Hosted MCP on Cloud Run (Alexa / agents)

Point an MCP Streamable HTTP client at `{cappy-api-url}/mcp/` with `Authorization: Bearer` = linked access token. The agent calls `search_catalog`, `portion_to_grams`, `write_food_entry`, and the other tools in [mcp-tools.md](mcp-tools.md). A client that only has an utterance calls the `interpret_meal` Firebase callable, not MCP. Cloud Run does not expose `/interpret_meal` as plain HTTP — only MCP + exchange.

### Manual token bootstrap (before OAuth pages exist)

1. Sign in with Firebase Auth (web or REST).
2. `POST {cappy-api-url}/exchange_access_token` or the `exchange_access_token` **callable** with `{"data":{"firebaseIdToken":"..."}}`.
3. Put returned `accessToken` in skill test **Access Token** field in the developer console, or use it in Lambda tests.

---

## 5. Checklist: zero → linked skill

### Firebase / GCP

- [ ] Confirm project `capy-dogfood`, region `us-central1` ([project.md](../infra/project.md)).
- [ ] Deploy functions: `npx -y firebase-tools@latest deploy --only functions --project capy-dogfood`.
- [ ] Set secrets: `API_ACCESS_TOKEN_SECRET`, `USDA_FDC_API_KEY` ([secrets-and-quotas.md](../runbooks/secrets-and-quotas.md)).
- [ ] Enable Auth providers used on the authorize page (Google, email/password).

### OAuth / account linking (ship before production linking)

- [ ] Register **Client ID** / **Client Secret** (Alexa console + server config).
- [ ] Deploy **authorize** page (Hosting) with Firebase Auth sign-in.
- [ ] Deploy **token** endpoint returning Cappy JWT (`access_token`, `expires_in`).
- [ ] Add Alexa **redirect URLs** and **domain** to console and Hosting.
- [ ] End-to-end test: link account in Alexa app → token works on `get_thread` with Bearer.

### Alexa skill

- [ ] Create skill (custom model or pre-built), note **skill ID**.
- [ ] Configure **Account Linking** (Auth Code Grant) with URIs above.
- [ ] Create **Lambda** (or Alexa-hosted endpoint) in `us-east-1` (Alexa requirement) that reads `accessToken` and calls callables.
- [ ] Map intents (e.g. `LogMealIntent`, `AskCappyIntent`) to `interpret_meal` / `log_meal`.
- [ ] Handle unlink: missing token → `withLinkAccountCard()`.
- [ ] Certification: privacy policy URL, mention Firebase-stored food/utterance data ([security.md](security.md)).

### Verify APIs

- [ ] `exchange_access_token` returns JWT.
- [ ] `interpret_meal` with `useServerContext: true` returns `assistantMessage`.
- [ ] `get_thread` returns `messages` + `pageInfo.nextCursor` for history.
- [ ] Token expiry (1h): plan re-link or implement `refresh_token` on token endpoint.

---

## Related docs

- [external-auth.md](external-auth.md) — Bearer tokens and `exchange_access_token`
- [mcp-tools.md](mcp-tools.md) — Tool names and payloads (mirror in skill code)
- [user-store.md](user-store.md) — Firestore data linked users see via server context
