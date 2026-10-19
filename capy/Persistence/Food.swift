import Foundation
import SwiftData

@Model
final class Food {
    @Attribute(.unique) var id: String
    var canonicalName: String
    var aliasesRaw: String
    var sourceRaw: String
    var usdaFdcId: Int?
    var caloriesPer100g: Double
    var proteinGPer100g: Double
    var carbsGPer100g: Double
    var fatGPer100g: Double
    /// USDA/overlay household serving grams; 0 = unknown.
    var servingGrams: Double = 0
    var servingLabel: String = ""
    var ingredientFamily: String
    var isComposite: Bool
    var cachedAt: Date

    var source: FoodSource {
        get { FoodSource(rawValue: sourceRaw) ?? .seed }
        set { sourceRaw = newValue.rawValue }
    }

    var aliases: [String] {
        get {
            aliasesRaw.split(separator: "|").map(String.init).filter { !$0.isEmpty }
        }
        set {
            aliasesRaw = newValue.joined(separator: "|")
        }
    }

    var per100g: MacroTotals {
        MacroTotals(
            calories: caloriesPer100g,
            proteinG: proteinGPer100g,
            carbsG: carbsGPer100g,
            fatG: fatGPer100g
        )
    }

    init(
        id: String,
        canonicalName: String,
        aliases: [String] = [],
        source: FoodSource = .seed,
        usdaFdcId: Int? = nil,
        per100g: MacroTotals,
        servingGrams: Double = 0,
        servingLabel: String = "",
        ingredientFamily: String,
        isComposite: Bool = false,
        cachedAt: Date = .now
    ) {
        self.id = id
        self.canonicalName = canonicalName
        self.aliasesRaw = aliases.joined(separator: "|")
        self.sourceRaw = source.rawValue
        self.usdaFdcId = usdaFdcId
        self.caloriesPer100g = per100g.calories
        self.proteinGPer100g = per100g.proteinG
        self.carbsGPer100g = per100g.carbsG
        self.fatGPer100g = per100g.fatG
        self.servingGrams = servingGrams
        self.servingLabel = servingLabel
        self.ingredientFamily = ingredientFamily
        self.isComposite = isComposite
        self.cachedAt = cachedAt
    }
}
