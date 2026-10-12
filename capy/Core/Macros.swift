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

/// Calorie → macro gram splits. LLM never owns this math.
enum MacroSplit: String, Codable, CaseIterable, Identifiable {
    case balanced
    case lowCarb
    case highProtein
    case custom

    var id: String { rawValue }

    var title: String {
        switch self {
        case .balanced: "Balanced"
        case .lowCarb: "Low Carb"
        case .highProtein: "High Protein"
        case .custom: "Custom"
        }
    }

    /// Protein / carbs / fat as fractions of calories. `nil` for custom.
    var calorieFractions: (protein: Double, carbs: Double, fat: Double)? {
        switch self {
        case .balanced: (0.30, 0.40, 0.30)
        case .lowCarb: (0.30, 0.20, 0.50)
        case .highProtein: (0.40, 0.30, 0.30)
        case .custom: nil
        }
    }

    var subtitle: String {
        guard let f = calorieFractions else {
            return "Set protein, carbs, and fat yourself"
        }
        return "\(pct(f.protein)) P · \(pct(f.carbs)) C · \(pct(f.fat)) F"
    }

    private func pct(_ value: Double) -> String {
        "\(Int((value * 100).rounded()))%"
    }
}

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
