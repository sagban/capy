import Foundation

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
