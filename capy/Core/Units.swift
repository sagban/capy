import Foundation
import SwiftUI

enum EnergyUnit: String, Codable, CaseIterable, Identifiable {
    case kcal
    case kilojoule

    var id: String { rawValue }

    var title: String {
        switch self {
        case .kcal: "Calories"
        case .kilojoule: "Kilojoules"
        }
    }

    var shortLabel: String {
        switch self {
        case .kcal: "cal"
        case .kilojoule: "kJ"
        }
    }

    var goalTitle: String {
        switch self {
        case .kcal: "Calories"
        case .kilojoule: "Energy"
        }
    }
}

enum FoodMassUnit: String, Codable, CaseIterable, Identifiable {
    case gram
    case ounce

    var id: String { rawValue }

    var title: String {
        switch self {
        case .gram: "Grams"
        case .ounce: "Ounces"
        }
    }

    var shortLabel: String {
        switch self {
        case .gram: "g"
        case .ounce: "oz"
        }
    }

    /// Default portion picker unit from settings weight preference.
    var defaultPortionUnit: PortionUnit {
        switch self {
        case .gram: .gram
        case .ounce: .ounce
        }
    }
}

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

enum BodyMassUnit: String, Codable, CaseIterable, Identifiable {
    case kilogram
    case pound

    var id: String { rawValue }

    var title: String {
        switch self {
        case .kilogram: "Kilograms"
        case .pound: "Pounds"
        }
    }

    var shortLabel: String {
        switch self {
        case .kilogram: "kg"
        case .pound: "lb"
        }
    }
}

enum WeekStartPreference: String, Codable, CaseIterable, Identifiable {
    case system
    case sunday
    case monday

    var id: String { rawValue }

    var title: String {
        switch self {
        case .system: "System"
        case .sunday: "Sunday"
        case .monday: "Monday"
        }
    }

    /// Calendar weekday (1 = Sunday … 7 = Saturday), or nil to use device default.
    var calendarWeekday: Int? {
        switch self {
        case .system: nil
        case .sunday: 1
        case .monday: 2
        }
    }
}

enum MeasurementSystem: String, Codable, CaseIterable, Identifiable {
    case metric
    case imperial

    var id: String { rawValue }

    var title: String {
        switch self {
        case .metric: "Metric"
        case .imperial: "Imperial"
        }
    }

    var foodMass: FoodMassUnit {
        switch self {
        case .metric: .gram
        case .imperial: .ounce
        }
    }

    var bodyMass: BodyMassUnit {
        switch self {
        case .metric: .kilogram
        case .imperial: .pound
        }
    }

    static func matching(food: FoodMassUnit, body: BodyMassUnit) -> MeasurementSystem? {
        if food == .gram && body == .kilogram { return .metric }
        if food == .ounce && body == .pound { return .imperial }
        return nil
    }
}

/// Display preferences. Core maths stay in kcal + grams.
struct UnitPreferences: Equatable {
    var energy: EnergyUnit
    var foodMass: FoodMassUnit
    var bodyMass: BodyMassUnit
    var weekStart: WeekStartPreference

    static let `default` = UnitPreferences(
        energy: .kcal,
        foodMass: .gram,
        bodyMass: .kilogram,
        weekStart: .system
    )

    private static let kjPerKcal = 4.184
    private static let gramsPerOunce = 28.349523125
    private static let poundsPerKilogram = 2.2046226218

    func energy(fromKcal kcal: Double) -> Double {
        switch energy {
        case .kcal: kcal
        case .kilojoule: kcal * Self.kjPerKcal
        }
    }

    func kcal(fromDisplay value: Double) -> Double {
        switch energy {
        case .kcal: value
        case .kilojoule: value / Self.kjPerKcal
        }
    }

    func foodMass(fromGrams grams: Double) -> Double {
        switch foodMass {
        case .gram: grams
        case .ounce: grams / Self.gramsPerOunce
        }
    }

    func grams(fromFoodMass value: Double) -> Double {
        switch foodMass {
        case .gram: value
        case .ounce: value * Self.gramsPerOunce
        }
    }

    func bodyMass(fromKilograms kg: Double) -> Double {
        switch bodyMass {
        case .kilogram: kg
        case .pound: kg * Self.poundsPerKilogram
        }
    }

    func formattedEnergy(_ kcal: Double, decimals: Int = 0) -> String {
        let value = energy(fromKcal: kcal)
        return "\(format(value, decimals: decimals)) \(energy.shortLabel)"
    }

    func formattedFoodMass(_ grams: Double, decimals: Int = 0) -> String {
        let value = foodMass(fromGrams: grams)
        return "\(format(value, decimals: decimals)) \(foodMass.shortLabel)"
    }

    func formattedMacroGrams(_ grams: Double) -> String {
        // Macro nutrients stay in grams (common in nutrition apps).
        "\(Int(grams.rounded())) g"
    }

    var firstWeekday: Int {
        weekStart.calendarWeekday ?? Calendar.current.firstWeekday
    }

    private func format(_ value: Double, decimals: Int) -> String {
        if decimals <= 0 {
            return "\(Int(value.rounded()))"
        }
        return String(format: "%.\(decimals)f", value)
    }
}

private struct UnitPreferencesKey: EnvironmentKey {
    static let defaultValue = UnitPreferences.default
}

extension EnvironmentValues {
    var unitPreferences: UnitPreferences {
        get { self[UnitPreferencesKey.self] }
        set { self[UnitPreferencesKey.self] = newValue }
    }
}
