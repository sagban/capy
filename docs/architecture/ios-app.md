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

**Capy confirm → Food Log:** confirming a `confirm_log` with multiple foods creates **one diary row (`MealEntry`) per food**, each with a single item — not one multi-item meal card. Reply copy may still say “logged A and B”. Correction/delete paths still target one existing entry/item. Manual Log multi-ingredient plates are unchanged.

**Capy confirm → Library:** accepted `web` / `estimate` (menu-cited) lines also upsert into Library as `kind=food`, `origin=aiGenerated`, keyed by `sourceFoodId` (= agent `foodId`). Stored macros are the confirmed portion; `servingGrams` is that portion weight so later `libraryContext` resolve stays consistent.

## Folder layout (target)

```text
capy/
  App/                 # CapyApp, AppContainer, root routing
  Domain/
    MealCommit/        # Shared diary writes (Capy confirm + Manual Log + library upsert)
  Core/                # Pure helpers (MacroMath, seed import, stores)
    Enums/             # Domain + wire enums (one type per file)
    Entity/            # Value structs (`MacroTotals`, `LibraryIngredientLine`, …)
    DTO/               # Codable request/response / queue payloads
    UIComponents/      # Shared SwiftUI rows/badges, loaders, motion helpers
  Persistence/         # SwiftData `@Model` types only (one type per file)
  Features/
    Auth/
    Onboarding/
    Capy/              # Chat UI + Confirm/ applier
      Confirm/         # ConfirmLine, CapyConfirmApplier, sheet types
    FoodLog/
    Library/           # Sheets/views (editor, picker, portion)
    Settings/
  AgentClient/         # Callable HTTP clients + sync services
  Resources/           # SeedFoods.json, GoldenCases.json
```

Colors/materials live under `Core/` (`CapyColors`, `CapyChrome`). Enums → `Core/Enums/`, struct entities → `Core/Entity/`, Codable DTOs → `Core/DTO/`. `Persistence/` is SwiftData `@Model` types only. Diary commits go through `Domain/MealCommit` (not feature views).

## Responsibilities

| Module | Owns |
|--------|------|
| `Domain/MealCommit` | Insert/update/delete diary rows, enqueue sync, AI library upsert on confirm |
| `Core` | Pure helpers, seed import, stores; unit-tested; no API keys |
| `Core/Enums` | Shared enums (one type per file) |
| `Core/Entity` | Value structs / snapshots (one type per file) |
| `Core/DTO` | Codable wire + queue payloads |
| `Persistence` | SwiftData `@Model` schema only |
| `AgentClient` | Auth token attach, HTTP clients, sync; never trusts macros |
| `Features/*` | SwiftUI screens; uses palette + system materials |
| `Core/UIComponents` | Shared SwiftUI rows/badges |

## Concurrency / DI

- Prefer `actor` for search/cache and network clients
- Inject services via `AppContainer` (protocols) for tests and emulators
- SwiftData `ModelContainer` registered at app root

## UI rules (see design docs)

- Native SwiftUI: `TabView`, `NavigationStack`, `List`, sheets, SF Symbols
- Liquid glass / system `Material` — subtle, HIG-aligned
- Colors only from [App Color Palette](../design/color-palette.md)
