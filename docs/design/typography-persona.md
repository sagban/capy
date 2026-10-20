# Typography, icon & Capy persona

## Fonts

**Ship with SF Rounded** (`Font.Design.rounded` via `capyTypography()` on the root). It matches warm parchment + moss: friendly without cartoon fonts or Inter/Roboto SaaS vibes.

| Role | Choice |
|------|--------|
| UI / chat / settings | SF Rounded (system) |
| Macro numbers | SF Rounded + `.monospacedDigit()` (`CapyTypography.metric`) |
| Optional later display | **Nunito** or **Sofia Sans** if you want a bundled logo wordmark only — keep UI on SF |

Avoid: heavy serif “editorial” stacks, geometric neo-grotesques, and handwriting scripts for body copy.

## App icon

**Glassmorphic Capy:** frosted geometric silhouette in brand colors — parchment cream, moss green glass, warm brown. Asset: `AppIcon.appiconset/AppIcon.png`. Avatar/launch resize from the same PNG. (`scripts/render_app_icon.swift` is an alternate flat geometric fallback.)

## Capy persona (visual + voice)

- **Look:** Same mark as the icon (`CapyAvatar` / `CapyLaunchIcon`).
- **Voice:** Doer, not coach — “logged”, “fits”, “left”. No streaks/shame. Warm sentences, never tool dumps.
- **Presence:** Toolbar circle avatar on Capy tab; typing dots while thinking.