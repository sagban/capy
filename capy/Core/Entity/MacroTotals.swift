import Foundation

struct MacroTotals: Equatable, Sendable, Codable {
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double

    static let zero = MacroTotals(calories: 0, proteinG: 0, carbsG: 0, fatG: 0)

    /// Remaining budget per macro, clamped at zero. Display must use this (or equivalent);
    /// never feed rounded display values back into calculation.
    static func remaining(target: MacroTotals, eaten: MacroTotals) -> MacroTotals {
        MacroTotals(
            calories: max(0, target.calories - eaten.calories),
            proteinG: max(0, target.proteinG - eaten.proteinG),
            carbsG: max(0, target.carbsG - eaten.carbsG),
            fatG: max(0, target.fatG - eaten.fatG)
        )
    }

    /// True when any macro eaten exceeds target (raw compare; remaining still clamps to 0).
    static func isOverBudget(target: MacroTotals, eaten: MacroTotals) -> Bool {
        eaten.calories > target.calories
            || eaten.proteinG > target.proteinG
            || eaten.carbsG > target.carbsG
            || eaten.fatG > target.fatG
    }

    /// Factual note when over target; empty when within budget. No coach language.
    static func overBudgetNote(target: MacroTotals, eaten: MacroTotals) -> String? {
        guard isOverBudget(target: target, eaten: eaten) else { return nil }
        var parts: [String] = []
        if eaten.calories > target.calories {
            parts.append("calories")
        }
        if eaten.proteinG > target.proteinG {
            parts.append("protein")
        }
        if eaten.carbsG > target.carbsG {
            parts.append("carbs")
        }
        if eaten.fatG > target.fatG {
            parts.append("fat")
        }
        return "0 left — \(parts.joined(separator: ", ")) over target"
    }

    static func + (lhs: MacroTotals, rhs: MacroTotals) -> MacroTotals {
        MacroTotals(
            calories: lhs.calories + rhs.calories,
            proteinG: lhs.proteinG + rhs.proteinG,
            carbsG: lhs.carbsG + rhs.carbsG,
            fatG: lhs.fatG + rhs.fatG
        )
    }

    var isOverBudget: Bool {
        false
    }
}
