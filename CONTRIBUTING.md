# Contributing

Capy is an iPhone meal log and a Python agent. The phone and an external MCP client write the same diary.

## Layout

- `app/` is the SwiftUI app. Open `app/capy.xcodeproj`. Tests are in `app/capyTests/`.
- `functions/agent/` is the meal agent and the tools both sides call.
- `functions/cloudrun/` is the Cloud Run process: `/healthz`, `/authenticate`, `/exchange_access_token`, and `/mcp/`.
- `functions/main.py` is the Firebase callables.
- `docs/architecture/api-contracts.md` is the request and response contract. A schema change updates that file in the same change. A harness graph change also updates `docs/architecture/harness.md`.

## Run

Python 3.12.

```bash
cd functions
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn cloudrun.app:app --host 127.0.0.1 --port 8080
```

The iPhone app uses `./run.sh` from the repo root, then the **capy Local** scheme in Xcode. `GoogleService-Info.plist` is not in git. Download it for your Firebase iOS app into `app/capy/`.

To point this checkout at a cloud project, edit `capy.env` and run `./configure.sh`. That file is the only cloud config. It writes `.firebaserc` and `app/Config/Secrets.xcconfig`. `./deploy.sh` reads it and writes the Cloud Run URL back into `CAPY_MCP_URL`.

## Tests

Offline. They do not call Vertex or USDA.

```bash
cd functions
./venv/bin/python -m pytest -q
```

## Secrets

Do not commit `.env`, `functions/.secret.local`, `GoogleService-Info.plist`, or API keys. USDA and the MCP signing secret stay in Secret Manager. Gemini uses Vertex credentials on the server. The iPhone binary does not contain those keys.

## Pull requests

One change per pull request. Say what a user can do afterward. If you change a tool argument or a callable body, update `docs/architecture/api-contracts.md` and, for MCP tools, `docs/architecture/mcp-tools.md`.
