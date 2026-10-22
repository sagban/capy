# App Color Palette

Pre-declared tokens. **No ad-hoc hex in SwiftUI views.** Use `Color.capy.*` (asset catalog / extensions) or semantic system colors where noted.

## Brand direction

Warm neutrals + a bright moss accent. Macro rings (calories / P / C / F) use saturated, easy-to-scan hues — not muted pastels. Avoid purple AI clichés, neon glow stacks, and cream+terracotta “AI landing page” tropes.

## Tokens

| Token | Role | Light (hex) | Dark (hex) |
|-------|------|-------------|------------|
| `capy.background` | App canvas | `#F3EFE7` | `#141210` |
| `capy.surface` | Grouped content / list rows | `#FFFCF7` | `#3A342E` |
| `capy.surfaceElevated` | Sheets / pick card base | `#FFFFFF` | `#4C453E` |
| `capy.textPrimary` | Titles, numbers | `#1F1B16` | `#F5F0E8` |
| `capy.textSecondary` | Supporting | `#6B645A` | `#B8B0A4` |
| `capy.accent` | Primary CTA / brand | `#1FA971` | `#3DDC97` |
| `capy.accentSoft` | Chips / soft fill | `#C6F0DC` | `#1A4A35` |
| `capy.warning` | Over-budget factual note | `#E67E22` | `#FFB020` |
| `capy.separator` | Hairlines if needed | use `Color(.separator)` | same |
| `capy.budgetCalories` | Calorie emphasis | `#FF4D3A` | `#FF6B5A` |
| `capy.budgetProtein` | Protein | `#FF5722` | `#FF7043` |
| `capy.budgetCarbs` | Carbs | `#2B7FFF` | `#5CA3FF` |
| `capy.budgetFat` | Fat | `#F5A524` | `#FFC14D` |

Accent in Xcode: map `AccentColor` → `capy.accent`.

## Materials / liquid glass

- Prefer system tab bar / toolbar materials (iOS liquid glass where available)
- Content panels: `.background(.ultraThinMaterial)` or `.regularMaterial` over `capy.background`
- Avoid multi-layer fake glass, heavy shadows, or glow
- Custom chrome only for Capy pick card + talk box if system components are insufficient

## Usage rules

1. Text → `capy.textPrimary` / `capy.textSecondary` (or `.primary` / `.secondary` when equivalent)
2. CTAs → `capy.accent`
3. Reason chips → `capy.accentSoft` fill + `capy.textPrimary`
4. Macro badges / goal rings → `capy.budget*` (keep saturated — don’t mute in views)
5. Never hardcode `#RRGGBB` in feature views

## Type and voice

UI text is SF Rounded (`capyTypography()`). Macro numbers use `.monospacedDigit()`. Copy uses logged, fits, and left. No streaks and no coach language.
