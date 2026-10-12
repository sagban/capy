# App Color Palette

Pre-declared tokens. **No ad-hoc hex in SwiftUI views.** Use `Color.capy.*` (asset catalog / extensions) or semantic system colors where noted.

## Brand direction

Calm, earthy, unbothered capybara — warm neutrals + a single moss/teal accent. Avoid purple AI clichés, neon glow, and cream+terracotta “AI landing page” tropes.

## Tokens

| Token | Role | Light (hex) | Dark (hex) |
|-------|------|-------------|------------|
| `capy.background` | App canvas | `#F3EFE7` | `#1C1A17` |
| `capy.surface` | Grouped content behind glass | `#FFFCF7` | `#2A2622` |
| `capy.surfaceElevated` | Sheets / pick card base | `#FFFFFF` | `#342F2A` |
| `capy.textPrimary` | Titles, numbers | `#1F1B16` | `#F5F0E8` |
| `capy.textSecondary` | Supporting | `#6B645A` | `#B8B0A4` |
| `capy.accent` | Primary CTA / brand | `#3F6F5A` | `#7FB89A` |
| `capy.accentSoft` | Chips / soft fill | `#D7E8DE` | `#2F4A3C` |
| `capy.warning` | Over-budget factual note | `#A15C2D` | `#E0A06A` |
| `capy.separator` | Hairlines if needed | use `Color(.separator)` | same |
| `capy.budgetCalories` | Calorie emphasis | `#3F6F5A` | `#7FB89A` |
| `capy.budgetProtein` | Protein | `#3D5A80` | `#8FB4D9` |
| `capy.budgetCarbs` | Carbs | `#8A6A3D` | `#D2B48C` |
| `capy.budgetFat` | Fat | `#7A4E6D` | `#C49BB3` |

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
4. Never hardcode `#RRGGBB` in feature views
