# Cappy backlog map

Tracked on GitHub: [sagban/capy](https://github.com/sagban/capy)

Phase 0 = infra + documentation only. Feature coding starts Phase 1 ∥ Phase 2 after Phase 0 artifacts exist.


## Phase 0 status (2026-10-11)

- Docs/design/rules/seed: **done** (issues #14–#28 closed).
- Firebase dogfood project: **`capy-dogfood`** with iOS app `sagar.capy`.
- [#13](https://github.com/sagban/capy/issues/13) closed: Google enabled; Apple Sign-In deferred.
- Phase 2 UI shell shipped (Auth → Onboarding → TabView). Harness wiring remains Phase 1/3.
- Details: [docs/infra/project.md](docs/infra/project.md)

## Milestones

| Milestone | Due | URL |
|-----------|-----|-----|
| Phase 0 — Infra and Docs | 2026-10-18 | https://github.com/sagban/capy/milestone/1 |
| Phase 1 — Harness Core | 2026-10-24 | https://github.com/sagban/capy/milestone/2 |
| Phase 2 — UI Core | 2026-10-24 | https://github.com/sagban/capy/milestone/3 |
| Phase 3 — Integration Loop | 2026-10-29 | https://github.com/sagban/capy/milestone/4 |
| Phase 4 — Polish and Evals | 2026-10-31 | https://github.com/sagban/capy/milestone/5 |
| Phase 5 — Post-October (P2) | — | https://github.com/sagban/capy/milestone/6 |

## Epics

| Epic | Issue | Milestone |
|------|-------|-----------|
| E0 Infra, docs, design | [#1](https://github.com/sagban/capy/issues/1) | Phase 0 |
| E1 Auth & platform wiring | [#2](https://github.com/sagban/capy/issues/2) | Phase 2 |
| E2 Deterministic nutrition core | [#3](https://github.com/sagban/capy/issues/3) | Phase 1 |
| E3 Food DB, seed, search/cache | [#4](https://github.com/sagban/capy/issues/4) | Phase 1 |
| E4 LangGraph AI harness | [#5](https://github.com/sagban/capy/issues/5) | Phase 1 |
| E5 Tab: Capy (AI screen) | [#6](https://github.com/sagban/capy/issues/6) | Phase 2 |
| E6 Tab: Food Log | [#7](https://github.com/sagban/capy/issues/7) | Phase 2 |
| E7 Tab: Library | [#8](https://github.com/sagban/capy/issues/8) | Phase 2 |
| E7b Settings (toolbar) | [#9](https://github.com/sagban/capy/issues/9) | Phase 2 |
| E8 Assistance dial & policy | [#10](https://github.com/sagban/capy/issues/10) | Phase 3 |
| E9 Golden evals & ship gates | [#11](https://github.com/sagban/capy/issues/11) | Phase 4 |
| E10 Post-October (P2) | [#12](https://github.com/sagban/capy/issues/12) | Phase 5 |

## Phase 0 — Infra and Docs

| Issue | Title |
|-------|-------|
| [#13](https://github.com/sagban/capy/issues/13) | [Infra] Provision Firebase project + iOS app + Auth (Apple, Google) |
| [#14](https://github.com/sagban/capy/issues/14) | [Infra] Secret Manager + Vertex Gemini + USDA key runbook |
| [#15](https://github.com/sagban/capy/issues/15) | [Infra] Emulator Suite layout + local secrets policy |
| [#16](https://github.com/sagban/capy/issues/16) | [Docs] System architecture overview + trust boundary |
| [#17](https://github.com/sagban/capy/issues/17) | [Docs] iOS app module architecture + TabView IA |
| [#18](https://github.com/sagban/capy/issues/18) | [Docs] LangGraph harness architecture |
| [#19](https://github.com/sagban/capy/issues/19) | [Docs] Data model document |
| [#20](https://github.com/sagban/capy/issues/20) | [Docs] API contracts (Pydantic ↔ Swift Codable) |
| [#21](https://github.com/sagban/capy/issues/21) | [Docs] Security + App Store privacy notes |
| [#22](https://github.com/sagban/capy/issues/22) | [Docs] Local development runbook |
| [#23](https://github.com/sagban/capy/issues/23) | [Docs] PRD mapping (FR-x → epic/issue) |
| [#24](https://github.com/sagban/capy/issues/24) | [Docs] Screen inventory — Capy / Food Log / Library / Settings |
| [#25](https://github.com/sagban/capy/issues/25) | [Design] App Color Palette + liquid-glass Material guide |
| [#26](https://github.com/sagban/capy/issues/26) | [Design] Figma — three tabs + Settings |
| [#27](https://github.com/sagban/capy/issues/27) | [Docs] Cursor rules (palette, native UI, no LLM macros) |
| [#28](https://github.com/sagban/capy/issues/28) | [Docs] Seed food / template inventory (content only) |

## Phase 1 — Harness Core

**Implementation note (2026-10-12):** Slice A/B landed in-tree — Core remaining/variety/verifier + dial policy (XCTest), seed importer + Manual Log catalog search, conversation + Muse-style long-term memory + ContextBuilder, Functions LangGraph/tools/USDA + `pytest` goldens. Full Capy↔callable chat wiring remains Phase 3 (#48). Evidence: `capyTests/*`, `functions/tests/test_harness_goldens.py`, docs `api-contracts.md` / `harness.md`.

| Issue | Title |
|-------|-------|
| [#29](https://github.com/sagban/capy/issues/29) | [Core] Remaining budget pure functions + clamp at zero |
| [#30](https://github.com/sagban/capy/issues/30) | [Core] Same-day variety filter + 7-day repetition decay |
| [#31](https://github.com/sagban/capy/issues/31) | [Core] Suggestion verifier ±10% all macros + abstain |
| [#32](https://github.com/sagban/capy/issues/32) | [Data] Seed catalog importer + local food cache schema |
| [#33](https://github.com/sagban/capy/issues/33) | [Data] USDA Foundation/SR Legacy fallback client |
| [#34](https://github.com/sagban/capy/issues/34) | [Harness] Define LangGraph state and node graph for meal intent |
| [#35](https://github.com/sagban/capy/issues/35) | [Harness] Gemini structured output schema for food+grams |
| [#36](https://github.com/sagban/capy/issues/36) | [Harness] Tools: search_food, propose_meal, calc_macros boundary |
| [#37](https://github.com/sagban/capy/issues/37) | [Harness] Explicit memory snapshot contract |
| [#38](https://github.com/sagban/capy/issues/38) | [Harness] Emulator runbook exercised + harness unit/contract tests |
| [#39](https://github.com/sagban/capy/issues/39) | [Both] Assistance dial policy matrix (pure policy) |

## Phase 2 — UI Core

| Issue | Title |
|-------|-------|
| [#40](https://github.com/sagban/capy/issues/40) | [UI] Auth screen — Apple and Google entry points |
| [#41](https://github.com/sagban/capy/issues/41) | [UI] Onboarding — targets, dial, starter preferences |
| [#42](https://github.com/sagban/capy/issues/42) | [UI] Main TabView shell + Settings toolbar |
| [#43](https://github.com/sagban/capy/issues/43) | [UI] Capy tab — budget, pick, talk box, confirm |
| [#44](https://github.com/sagban/capy/issues/44) | [UI] Food Log tab — goals, day switcher, insights, log |
| [#45](https://github.com/sagban/capy/issues/45) | [UI] Library tab — custom + AI-generated items |
| [#46](https://github.com/sagban/capy/issues/46) | [UI] Settings — goals, prefs, diets, Capy dial, user |
| [#47](https://github.com/sagban/capy/issues/47) | [UI] Manual food search / log from Food Log or Library |

## Phase 3 — Integration Loop

| Issue | Title |
|-------|-------|
| [#48](https://github.com/sagban/capy/issues/48) | [Both] Wire Capy talk box ↔ authenticated callable ↔ LangGraph |
| [#49](https://github.com/sagban/capy/issues/49) | [Core] On-device deterministic maths as source of truth |
| [#50](https://github.com/sagban/capy/issues/50) | [UI] Confirm-before-persist logging + correction deltas |
| [#51](https://github.com/sagban/capy/issues/51) | [Core] Suggestion pipeline templates → variety → verify → abstain |
| [#52](https://github.com/sagban/capy/issues/52) | [Both] Dial enforcement in-app (Full Assist / Guided / Quiet) |
| [#53](https://github.com/sagban/capy/issues/53) | [Dogfood] First open → log → suggestion in under 2 minutes |

## Phase 4 — Polish and Evals

| Issue | Title |
|-------|-------|
| [#54](https://github.com/sagban/capy/issues/54) | [Eval] Golden set ≥90% + Indian composites + variety |
| [#55](https://github.com/sagban/capy/issues/55) | [Eval] Dial evals: Quiet silence + Full Assist benefit + no coach vocab |
| [#56](https://github.com/sagban/capy/issues/56) | [Eval] Zero unverified macros ship gate |
| [#57](https://github.com/sagban/capy/issues/57) | [UI] Accessibility / Dynamic Type pass on core screens |
| [#58](https://github.com/sagban/capy/issues/58) | [Docs] Risk gates: name/trademark + first non-tracker test |

## Phase 5 — Post-October (P2)

| Issue | Title |
|-------|-------|
| [#59](https://github.com/sagban/capy/issues/59) | [P2] Inventory-aware picks (FR-9) |
| [#60](https://github.com/sagban/capy/issues/60) | [P2] HealthKit dynamic budgets (FR-10) |
| [#61](https://github.com/sagban/capy/issues/61) | [P2] Grocery lists from low stock |
| [#62](https://github.com/sagban/capy/issues/62) | [P2] Native workout logging (only if pulled) |
| [#63](https://github.com/sagban/capy/issues/63) | [P2] Adaptive dial step-up / step-down (propose-and-confirm) |

## Locked product decisions

- Firebase Auth: **Sign in with Apple** + **Google Sign-In**
- Backend: Python Firebase Functions + **LangGraph** + **Gemini** (keys server-side only)
- IA: **TabView** — Capy (default) / Food Log / Library; **Settings** top-right
- UI: native SwiftUI + Apple liquid-glass/materials; fixed **App Color Palette**
- Verifier: calories ≤ remaining; every macro within ±10%; abstain when needed
- Memories/prefs/diets: explicit / user-editable only
- LLM never owns macro arithmetic

## Issue templates

Under [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/): Feature, Harness contract, UI screen, Infra, Docs, Eval.

## Scripts

- [`scripts/seed_github_backlog.sh`](scripts/seed_github_backlog.sh) — initial seed (already run)
- [`scripts/fix_issue_deps.py`](scripts/fix_issue_deps.py) — dependency cleanup helper
