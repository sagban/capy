import Foundation

enum MacroMath {
    static let kcalPerGramProtein = 4.0
    static let kcalPerGramCarbs = 4.0
    static let kcalPerGramFat = 9.0

    static func scale(per100g: MacroTotals, grams: Double) -> MacroTotals {
        let factor = grams / 100.0
        return MacroTotals(
            calories: per100g.calories * factor,
            proteinG: per100g.proteinG * factor,
            carbsG: per100g.carbsG * factor,
            fatG: per100g.fatG * factor
        )
    }

    /// Deterministic grams from calorie target + split. Custom returns `nil`.
    static func macros(calories: Double, split: MacroSplit) -> MacroTotals? {
        guard let fractions = split.calorieFractions else { return nil }
        return MacroTotals(
            calories: calories,
            proteinG: (calories * fractions.protein / kcalPerGramProtein).rounded(),
            carbsG: (calories * fractions.carbs / kcalPerGramCarbs).rounded(),
            fatG: (calories * fractions.fat / kcalPerGramFat).rounded()
        )
    }
}
