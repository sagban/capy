import Foundation
import SwiftUI

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
