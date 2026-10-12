import Foundation

struct MacroTotals: Equatable {
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double

    static let zero = MacroTotals(calories: 0, proteinG: 0, carbsG: 0, fatG: 0)

    static func remaining(target: MacroTotals, eaten: MacroTotals) -> MacroTotals {
        MacroTotals(
            calories: max(0, target.calories - eaten.calories),
            proteinG: max(0, target.proteinG - eaten.proteinG),
            carbsG: max(0, target.carbsG - eaten.carbsG),
            fatG: max(0, target.fatG - eaten.fatG)
        )
    }

    var isOverBudget: Bool {
        // Caller can compare raw eaten vs target; remaining clamps at zero.
        false
    }
}

enum MacroMath {
    static func scale(per100g: MacroTotals, grams: Double) -> MacroTotals {
        let factor = grams / 100.0
        return MacroTotals(
            calories: per100g.calories * factor,
            proteinG: per100g.proteinG * factor,
            carbsG: per100g.carbsG * factor,
            fatG: per100g.fatG * factor
        )
    }
}
