import Foundation
import SwiftData

@Model
final class MealEntryItem {
    var name: String
    var grams: Double
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    /// Catalog food id when known (variety / corrections).
    var foodId: String = ""
    /// Ingredient family snapshot for same-day variety hard filter.
    var ingredientFamily: String = ""
    /// catalog, usda, usda_branded, web, estimate, or diary.
    var source: String = ""
    var entry: MealEntry?

    init(
        name: String,
        grams: Double,
        calories: Double,
        proteinG: Double,
        carbsG: Double,
        fatG: Double,
        foodId: String = "",
        ingredientFamily: String = "",
        source: String = ""
    ) {
        self.name = name
        self.grams = grams
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
        self.foodId = foodId
        self.ingredientFamily = ingredientFamily
        self.source = source
    }

    /// Per-100g macros derived from logged totals and grams.
    var per100gMacros: MacroTotals? {
        guard grams > 0 else { return nil }
        return MacroTotals(
            calories: calories / grams * 100,
            proteinG: proteinG / grams * 100,
            carbsG: carbsG / grams * 100,
            fatG: fatG / grams * 100
        )
    }
}
