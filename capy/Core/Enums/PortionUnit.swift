import Foundation

/// Units for logging a portion (Foodnoms-style). Stored macros still use grams.
enum PortionUnit: String, CaseIterable, Identifiable {
    case gram
    case milliliter
    case ounce
    case teaspoon
    case tablespoon
    case cup
    case serving

    var id: String { rawValue }

    var title: String {
        switch self {
        case .gram: "Grams"
        case .milliliter: "Milliliters"
        case .ounce: "Ounces"
        case .teaspoon: "Teaspoon"
        case .tablespoon: "Tablespoon"
        case .cup: "Cup"
        case .serving: "Serving"
        }
    }

    var shortLabel: String {
        switch self {
        case .gram: "g"
        case .milliliter: "ml"
        case .ounce: "oz"
        case .teaspoon: "tsp"
        case .tablespoon: "tbsp"
        case .cup: "cup"
        case .serving: "serving"
        }
    }

    var fractionDigits: Int {
        switch self {
        case .gram, .milliliter: 0
        case .ounce, .teaspoon, .tablespoon, .cup, .serving: 1
        }
    }

    /// Grams represented by 1.0 of this unit. `servingGrams` is the food’s reference serving (usually `baseGrams`).
    func gramsPerUnit(servingGrams: Double) -> Double {
        switch self {
        case .gram: 1
        // Volume ≈ water density; enough for logging until food-specific density exists.
        case .milliliter: 1
        case .ounce: 28.349523125
        case .teaspoon: 4.92892
        case .tablespoon: 14.7868
        case .cup: 236.588
        case .serving: max(servingGrams, 1)
        }
    }

    func amount(fromGrams grams: Double, servingGrams: Double) -> Double {
        grams / gramsPerUnit(servingGrams: servingGrams)
    }

    func grams(fromAmount amount: Double, servingGrams: Double) -> Double {
        amount * gramsPerUnit(servingGrams: servingGrams)
    }
}
