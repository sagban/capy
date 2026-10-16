# System architecture overview

Cappy is an iPhone calorie tracker with an agent front door. **Code owns trusted gram scaling and displayed totals.** The meal LLM interprets language into tool calls. A grounded web lookup may normalize a cited serving to per 100 g; the harness still gates that density (citation + Atwater) before commit.

```text
┌─────────────────────────────────────────────────────────────┐
│  iOS app (SwiftUI + SwiftData)                              │
│  TabView: Food Log | Capy | Library  +  Settings (toolbar)  │
│                                                             │
│  ┌──────────────┐  ┌─────────────────┐  ┌───────────────┐ │
│  │ AgentClient  │  │ Deterministic   │  │ Local store   │ │
│  │ (callable)   │  │ Core (macros,   │  │ SwiftData     │ │
│  │              │  │ remaining,      │  │ foods, logs,  │ │
│  │              │  │ verify, dial)   │  │ memories)     │ │
│  └──────┬───────┘  └────────▲────────┘  └───────▲───────┘ │
└─────────┼───────────────────┼───────────────────┼─────────┘
          │ ID token          │ never trust LLM   │
          ▼                   │ macros            │
┌─────────────────────┐       │                   │
│ Firebase Auth       │       │                   │
│ Apple + Google      │       │                   │
└─────────┬───────────┘       │                   │
          ▼                   │                   │
┌─────────────────────┐       │                   │
│ Cloud Functions     │───────┘                   │
│ (Python 2nd gen)    │  returns intent / foods / │
│ LangGraph harness   │  grams / clarify only     │
│ Gemini structured   │                           │
│ USDA fallback       │◄── Secret Manager keys    │
└─────────────────────┘
```

## Trust boundary

| Layer | Allowed | Forbidden |
|-------|---------|-----------|
| LLM / LangGraph | Intent, food refs, grams or ambiguity, corrections, clarify questions; web path may normalize cited servings to per 100 g | Stating diary/suggestion totals as fact; inventing density without a citation |
| Deterministic core (Swift) | Portion scaling, remaining maths, variety filter, verifier, ranking | Calling Gemini |
| UI | Display verified numbers only | Showing model-claimed macros |

## Environments

| Env | Purpose |
|-----|---------|
| Local emulators | Auth + Functions for dogfood |
| Firebase / GCP `PROJECT_ID` | Dev/dogfood (see [../runbooks/local-dev.md](../runbooks/local-dev.md)) |

## Related docs

- [ios-app.md](ios-app.md) — modules + TabView IA
- [harness.md](harness.md) — LangGraph
- [data-model.md](data-model.md)
- [user-store.md](user-store.md) — Firestore profile + diary (server context)
- [api-contracts.md](api-contracts.md)
- [external-auth.md](external-auth.md) — HTTP / MCP tokens
- [alexa-setup.md](alexa-setup.md) — Alexa account linking
- [security.md](security.md)
