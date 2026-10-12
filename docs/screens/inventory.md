# Screen inventory

Locked IA: **TabView** — Capy (default) / Food Log / Library; **Settings** via top-trailing gear.

## Insights (V1 scope decision)

**Light V1:** Insights is a button on Food Log that opens a simple sheet: week calories average + days logged count. Full charts deferred to post-October.

---

## Auth

| | |
|--|--|
| **Purpose** | Sign in with Apple or Google |
| **Entry** | Cold start if no Firebase session |
| **Exit** | Onboarding (first run) or Main TabView |
| **States** | Idle, loading, provider cancel, error |
| **PRD** | Platform prerequisite |

## Onboarding

| | |
|--|--|
| **Purpose** | Set calorie/PCF targets, assistance dial, starter prefs/diet |
| **Entry** | First authenticated session |
| **Exit** | Main TabView (`onboardingCompleted`) |
| **States** | Form validation |
| **PRD** | FR-8 seed |

## Tab: Capy (AI)

| | |
|--|--|
| **Purpose** | Remaining budget, one verified pick + reasons, talk box |
| **Entry** | Default tab |
| **Exit** | Confirmation sheet; Log/Swap/Not this; Settings |
| **States** | Empty (no pick), loading interpret, offline, abstention, error |
| **PRD** | Core experience; FR-1, FR-3, FR-7 |

### Flows

1. **Activation:** ask → answer → bookkeep (confirm) → payback (budget / pick)
2. **Correction:** “half the rice” → recompute → show delta
3. **Suggest:** Log it / Swap it / Not this (Swap re-runs verified search)

## Tab: Food Log

| | |
|--|--|
| **Purpose** | Goals strip, day switcher, meal list, Insights |
| **Entry** | Tab 2 |
| **Exit** | Edit entry sheet; manual add; Insights sheet; Settings |
| **States** | Empty day, loading, over-budget factual note |
| **PRD** | FR-8 |

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
| Goals | Daily calorie + PCF |
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
