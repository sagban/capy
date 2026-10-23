import Foundation
import SwiftData

@Model
final class DailyTarget {
    var effectiveDate: Date
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    /// Defaults for lightweight migration when older stores lack this field.
    var splitRaw: String = MacroSplit.balanced.rawValue

    var macroSplit: MacroSplit {
        get { MacroSplit(rawValue: splitRaw) ?? .custom }
        set { splitRaw = newValue.rawValue }
    }

    init(
        effectiveDate: Date = Calendar.current.startOfDay(for: .now),
        calories: Double = 2000,
        proteinG: Double = 140,
        carbsG: Double = 200,
        fatG: Double = 65,
        macroSplit: MacroSplit = .balanced
    ) {
        self.effectiveDate = effectiveDate
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
        self.splitRaw = macroSplit.rawValue
    }
}
