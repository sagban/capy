# iOS app module architecture

## Platform

- **iPhone only** for V1 (narrow from current multiplatform template in Phase 1+)
- Target: iOS 18+ preferred; document actual deployment when project is trimmed
- Bundle ID (working): `sagar.capy`
- Observation framework (`@Observable`) for app state; configure Firebase in `App.init()` before any Auth-dependent state

## Navigation (locked IA)

```text
Auth → Onboarding (first run) → Main TabView
                                      ├─ Tab 1: Food Log      [default]
                                      ├─ Tab 2: Capy (AI)
                                      └─ Tab 3: Library
                                 Settings (top-right toolbar) → stack
```


Settings is **not** a tab. Use `NavigationStack` per tab; gear in `.toolbar` trailing.

## Folder layout (target)

```text
capy/
  App/                 # CapyApp, AppContainer, root routing
  Core/                # Pure macros, remaining, variety, verifier (no SwiftUI/network)
  Persistence/         # SwiftData models, repositories, seed import
  Features/
    Auth/
    Onboarding/
    Capy/              # Agentic screen
    FoodLog/
    Library/
    Settings/
  AgentClient/         # Callable HTTP + Codable DTOs
  DesignSystem/        # App Color Palette wrappers, materials helpers
  Resources/           # SeedFoods.json, GoldenCases.json
```

## Responsibilities

| Module | Owns |
|--------|------|
| `Core` | Pure functions; unit-tested; no API keys |
| `Persistence` | SwiftData schema, queries, macro snapshots on log items |
| `AgentClient` | Auth token attach, decode structured responses; never trusts macros |
| `Features/*` | SwiftUI screens; uses palette + system materials |
| `DesignSystem` | `Color.capy.*` tokens, glass/material helpers |

## Concurrency / DI

- Prefer `actor` for search/cache and network clients
- Inject services via `AppContainer` (protocols) for tests and emulators
- SwiftData `ModelContainer` registered at app root

## UI rules (see design docs)

- Native SwiftUI: `TabView`, `NavigationStack`, `List`, sheets, SF Symbols
- Liquid glass / system `Material` — subtle, HIG-aligned
- Colors only from [App Color Palette](../design/color-palette.md)
