# System architecture overview

Cappy is an iPhone calorie tracker with an agent front door. **Deterministic Swift code owns all nutrition arithmetic.** The LLM only interprets language into structured food/portion intents.

```text
┌─────────────────────────────────────────────────────────────┐
│  iOS app (SwiftUI + SwiftData)                              │
│  TabView: Capy | Food Log | Library  +  Settings (toolbar)  │
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
| LLM / LangGraph | Intent, food refs, grams or ambiguity, corrections, clarify questions | Stating calorie/PCF totals as fact |
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
- [api-contracts.md](api-contracts.md)
- [security.md](security.md)
