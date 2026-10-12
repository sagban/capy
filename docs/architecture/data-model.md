# Data model

Local authority: **SwiftData**. Reserved inventory entity exists for Phase 5 (FR-9) without V1 UI.

## Entities

### Food
- `id`, `canonicalName`, `aliases[]`
- `source`: seed | usda | user | ai_generated
- `usdaFdcId?`
- Per 100g: `calories`, `proteinG`, `carbsG`, `fatG`
- `ingredientFamily` (for same-day variety hard filter)
- `isComposite` (manual Indian/mixed dishes — LLM never invents macros)
- Cache timestamps

### CompositeIngredient
- `compositeFood` → `componentFood`, `grams`

### MealType
- `name`, `sortOrder`, `isEnabled`, `isSystem`
- Defaults seeded: Breakfast, Lunch, Snacks, Dinner (system — can disable, not delete)
- User can add custom types; only custom types are deletable

### MealEntry
- `timestamp`, `day` (calendar day key), `mealSlot?` (matches `MealType.name`)
- `originalUserText?`
- `confirmed: Bool`
- Items: `MealEntryItem[]`

### MealEntryItem
- `food`, `grams`
- **Macro snapshot** at confirm time (calories/PCF) — history must not rewrite when Food DB changes

### DailyTarget
- `effectiveDate`, `calories`, `proteinG`, `carbsG`, `fatG`
- `macroSplit`: `balanced` | `lowCarb` | `highProtein` | `custom`
- Preset splits compute P/C/F grams from calories in Swift `MacroMath` (never LLM)
- Target changes **never** rewrite past days

### MealTemplate (regulars)
- Named meal used by suggestion engine
- `MealTemplateItem[]` (food + default grams)

### LibraryItem
- User custom **Meal / Recipe / Food**
- `origin`: user | ai_generated
- Links to foods/grams or composite definition

### ExplicitMemory / Preferences
- Preferences, dislikes, allergies, diets
- User-editable only (Settings + Library)

### LongTermMemoryNote (Muse-style)
- Durable freeform facts that may not fit prefs/goals
- `id`, `text`, `createdAt`, `updatedAt`, `source`: user | agent
- Editable in Capy **Memory** sheet; agent may propose add/update/delete

### ConversationThread / ConversationTurn
- Singleton long-running Capy chat
- Thread: `summary`, `updatedAt`
- Turn: `role` (user|assistant), `text`, optional `structuredPayload` (working memory)

### AppSettings
- Assistance dial: `fullAssist` | `guided` | `quiet`
- Evening check-in time (Guided)
- Onboarding completed flag
- Units (display only; storage stays kcal + grams):
  - `energyUnit`: `kcal` | `kilojoule`
  - `foodMassUnit`: `gram` | `ounce` (settings default; log portion also supports ml / tsp / tbsp / cup / servings)
  - `bodyMassUnit`: `kilogram` | `pound`
- Regional: `weekStart`: `system` | `sunday` | `monday` (Food Log calendar); region/number formats follow device locale

### SearchCache
- Normalized query, result food ids, day, hit/miss

### InventoryItem (reserved, P2)
- `foodID`, `gramsOnHand`, `updatedAt` — no V1 UI

## Remaining maths

`remaining = max(0, target − sum(today's item snapshots))` per macro. Display rounding must not feed calculations.
