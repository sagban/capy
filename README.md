# Capy

iPhone meal log with a Python agent. The same diary writes are available over MCP.

## Introduction

Capy records meals on iPhone. You describe what you ate. The agent looks up the food, converts the portion to grams, and writes one diary entry. Calories, protein, carbs, and fat come from that food’s `per100g` and are scaled by grams / 100.

The iPhone uses Firebase callables. An external agent uses the Cloud Run app in `functions/cloudrun/`, which mounts `functions/cloudrun/mcp/host.py` at `POST /mcp/` (Streamable HTTP, spec 2025-11-25). Both paths write the same diary.

## What it does

- Food Log, Capy conversation, and Library on iPhone.
- Shared tools: `search_catalog`, `search_usda`, `search_library`, `lookup_barcode`, `portion_to_grams`, `get_diary`, `write_food_entry`, `delete_food_entry`, plus profile and library edits. Arguments are in [docs/architecture/mcp-tools.md](docs/architecture/mcp-tools.md).
- `write_food_entry` logs one entry. A second food is a second call.
- On iPhone, the first write waits until you confirm the same food id, grams, and `per100g`. MCP writes on the call.
- `GET /authenticate` on the API host signs you in with the same email and password as the app and returns a bearer plus an MCP client config. The token lasts one hour.

Logging one food is `search_catalog` (or USDA, library, or barcode), then `portion_to_grams` with that hit’s measures, then `write_food_entry` with `day_key`, `meal_slot`, `kind`, `name`, `grams`, `foodId`, `source`, and `per100g` copied from the hit. A later turn uses `get_diary` for that day, then `write_food_entry` again or `delete_food_entry`.

## How to run

Python 3.12. The seed catalog does not need API keys.

```bash
cd functions
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn cloudrun.app:app --host 127.0.0.1 --port 8080
```

- Health: `GET http://127.0.0.1:8080/healthz`
- MCP: `POST http://127.0.0.1:8080/mcp/` with `Accept: application/json, text/event-stream` and `Authorization: Bearer <token>`. Keep the trailing slash. A request without a bearer returns `401`.

Cloud settings live in one file, `capy.env`. Copy `capy.env.example` to `capy.env`, set `CAPY_GCP_PROJECT`, and put `GoogleService-Info.plist` in `app/capy/`. Then run `./configure.sh`. It writes `.firebaserc` and `app/Config/Secrets.xcconfig`. `./deploy.sh` uses the same file and fills in `CAPY_MCP_URL` when Cloud Run is up.

For the iPhone app, open `app/capy.xcodeproj`. The **capy Local** scheme talks to the Firebase emulators (`./run.sh` from the repo root). The **capy Prod** scheme talks to the deployed Firebase project. `GoogleService-Info.plist` is not in git.

## Testing

Offline. These tests do not call Vertex or USDA.

```bash
cd functions
./venv/bin/python -m pytest tests/test_jobs.py tests/test_tool_schema.py -q
```

## Repository

| Path | What it is |
|------|------------|
| `app/` | iPhone app. Open `app/capy.xcodeproj`. |
| `functions/agent/` | Meal agent: graph, prompts, and the shared diary tools. |
| `functions/cloudrun/` | Cloud Run host. MCP at `/mcp/`, sign-in at `/authenticate`. |
| `functions/main.py` | Firebase callables the iPhone uses, including `interpret_meal`. |
| `docs/` | API contract, harness, MCP tools, screens, and the local runbook. |

`./run.sh` starts the local Firebase emulators for the **capy Local** scheme. `./deploy.sh` deploys the callables and Cloud Run.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The license is [MIT](LICENSE). Copyright 2026 Sagar Bansal.
