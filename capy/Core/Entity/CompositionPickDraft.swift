import Foundation

/// Value snapshot for navigating pick → portion (SwiftData models aren’t path-friendly).
struct CompositionPickDraft: Hashable, Identifiable {
    var id: String
    var name: String
    var detail: String
    var foodId: String
    var servingGrams: Double
    var caloriesPer100g: Double
    var proteinGPer100g: Double
    var carbsGPer100g: Double
    var fatGPer100g: Double
    var source: LibraryIngredientSource
    var libraryKindRaw: String
    /// Working quantity in grams.
    var grams: Double
    /// When editing an existing composition line.
    var existingLineId: String?

    var per100g: MacroTotals {
        MacroTotals(
            calories: caloriesPer100g,
            proteinG: proteinGPer100g,
            carbsG: carbsGPer100g,
            fatG: fatGPer100g
        )
    }

    var macros: MacroTotals {
        MacroMath.scale(per100g: per100g, grams: grams)
    }

    static func from(food: Food) -> CompositionPickDraft {
        let serving: Double = {
            if food.servingGrams > 0 { return food.servingGrams }
            return PortionDefaults.servingGrams(
                family: food.ingredientFamily,
                name: food.canonicalName,
                kcalPer100g: food.caloriesPer100g
            )
        }()
        return CompositionPickDraft(
            id: food.id,
            name: food.canonicalName,
            detail: food.servingLabel.isEmpty ? food.ingredientFamily : food.servingLabel,
            foodId: food.id,
            servingGrams: serving,
            caloriesPer100g: food.caloriesPer100g,
            proteinGPer100g: food.proteinGPer100g,
            carbsGPer100g: food.carbsGPer100g,
            fatGPer100g: food.fatGPer100g,
            source: .catalogFood,
            libraryKindRaw: "",
            grams: serving,
            existingLineId: nil
        )
    }

    static func from(libraryItem item: LibraryItem) -> CompositionPickDraft {
        let line = LibraryIngredientLine.from(libraryItem: item, servings: 1)
        return CompositionPickDraft(
            id: item.uuidString,
            name: item.name,
            detail: item.kind.title,
            foodId: item.uuidString,
            servingGrams: line.servingGrams,
            caloriesPer100g: line.caloriesPer100g,
            proteinGPer100g: line.proteinGPer100g,
            carbsGPer100g: line.carbsGPer100g,
            fatGPer100g: line.fatGPer100g,
            source: .libraryItem,
            libraryKindRaw: item.kind.rawValue,
            grams: line.grams,
            existingLineId: nil
        )
    }

    static func from(line: LibraryIngredientLine) -> CompositionPickDraft {
        CompositionPickDraft(
            id: line.id,
            name: line.name,
            detail: line.libraryKind?.title ?? "",
            foodId: line.foodId,
            servingGrams: line.servingGrams,
            caloriesPer100g: line.caloriesPer100g,
            proteinGPer100g: line.proteinGPer100g,
            carbsGPer100g: line.carbsGPer100g,
            fatGPer100g: line.fatGPer100g,
            source: line.source,
            libraryKindRaw: line.libraryKindRaw,
            grams: line.grams,
            existingLineId: line.id
        )
    }

    func asIngredientLine() -> LibraryIngredientLine {
        LibraryIngredientLine(
            id: existingLineId ?? UUID().uuidString,
            foodId: foodId,
            name: name,
            grams: grams,
            servingGrams: servingGrams,
            caloriesPer100g: caloriesPer100g,
            proteinGPer100g: proteinGPer100g,
            carbsGPer100g: carbsGPer100g,
            fatGPer100g: fatGPer100g,
            source: source,
            libraryKindRaw: libraryKindRaw
        )
    }
}
