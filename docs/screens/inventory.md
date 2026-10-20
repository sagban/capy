# Screen inventory

Locked IA: **TabView** — Food Log (default) / Capy / Library; **Settings** via top-trailing gear.

## Insights (V1 scope decision)

**Light V1:** Insights is a button on Food Log that opens a simple sheet: week calories average + days logged count. Full charts deferred to post-October.

---

## Auth

| | |
|--|--|
| **Purpose** | Sign in with email + password or Google (Apple deferred). Email mode toggles sign in / create account; forgot password sends a Firebase reset link |
| **Entry** | Cold start if no Firebase session |
| **Exit** | Onboarding (first run) or Main TabView |
| **States** | Idle, loading, provider cancel, error |
| **PRD** | Platform prerequisite |

## Onboarding

| | |
|--|--|
| **Purpose** | Friendly one-question-at-a-time setup: calories, macro style, assistance dial, diets, likes, allergies |
| **Entry** | First authenticated session |
| **Exit** | Main TabView (`onboardingCompleted`) after Ready → Open Food Log |
| **States** | Step progress; optional chips Skip / None; defaults on calories/macros/dial |
| **PRD** | FR-8 seed |

## Tab: Food Log

| | |
|--|--|
| **Purpose** | Day navigator (‹ Today › + calendar), goals, meal list, Insights |
| **Entry** | Default tab |
| **Exit** | Goal metric detail (Day/Week/Month charts); Edit entry sheet; manual add; Insights sheet; Settings |
| **States** | Empty day, loading, over-budget factual note |
| **PRD** | FR-8 |

### Manual Log — barcode scanner

| | |
|--|--|
| **Purpose** | Scan a packaged-food GTIN → Open Food Facts → portion / log (same details sheet as catalog picks) |
| **Entry** | Manual Log “Scan barcode” (next to Add custom food) |
| **Exit** | Hit → save to Library (Foods) + Log food details; miss → Search or Add custom food; Cancel |
| **States** | Camera permission, unsupported device, looking up, not found |
| **PRD** | Supports FR-8 logging |

## Tab: Capy (AI)

| | |
|--|--|
| **Purpose** | Remaining budget, one verified pick + reasons, talk box |
| **Entry** | Tab 2 |
| **Exit** | Confirmation sheet; Log/Swap/Not this; Settings |
| **States** | Empty (no pick), loading interpret, offline, abstention, error |
| **PRD** | Core experience; FR-1, FR-3, FR-7 |

### Flows

1. **Activation:** ask → answer → bookkeep (confirm) → payback (budget / pick)
2. **Correction:** “half the rice” → recompute → show delta
3. **Suggest:** Log it / Swap it / Not this (Swap re-runs verified search)
4. **Confirm → Library:** accepted menu-cited (`web` / `estimate`) foods land under Library → Foods → AI-generated

## Tab: Library

| | |
|--|--|
| **Purpose** | Custom Meals / Recipes / Foods + AI-generated section |
| **Entry** | Tab 3 |
| **Exit** | Editor; use in log / Capy |
| **States** | Empty library |
| **PRD** | Supports FR-1 templates / customs |

## Settings (toolbar)

| Section | Content |
|---------|---------|
| Regional & units (General) | Week start; energy / food / body units |
| Goals | Daily calorie + PCF + macro split |
| Meal types | Enable/disable defaults; add custom |
| Food preferences | Likes / dislikes / allergies (explicit) |
| Diets | Diet tags |
| Capy Settings | Assistance dial + Guided check-in time |
| User details | Account provider, sign out |

Target edits never rewrite past days.

## Copy rules

- Doer verbs: logged, handled, fits, left, eat this
- Ban: coach, streak-shame, motivation lectures
- Medical / ED / pregnancy → “talk to a professional”, no meal pick

## Accessibility

- VoiceOver labels on budget numbers and Log/Swap/Not this
- Dynamic Type on tabs and primary actions
- Contrast via App Color Palette + system materials
