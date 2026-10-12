import Foundation
import SwiftData

enum FoodSource: String, Codable, CaseIterable {
    case seed
    case usda
    case user
    case aiGenerated
}

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
        self.ingredientFamily = ingredientFamily
        self.isComposite = isComposite
        self.cachedAt = cachedAt
    }
}

@Model
final class MealTemplate {
    @Attribute(.unique) var id: String
    var name: String
    @Relationship(deleteRule: .cascade, inverse: \MealTemplateItem.template)
    var items: [MealTemplateItem]

    init(id: String, name: String, items: [MealTemplateItem] = []) {
        self.id = id
        self.name = name
        self.items = items
    }
}

@Model
final class MealTemplateItem {
    var foodId: String
    var grams: Double
    var template: MealTemplate?

    init(foodId: String, grams: Double) {
        self.foodId = foodId
        self.grams = grams
    }
}

@Model
final class SearchCacheEntry {
    @Attribute(.unique) var normalizedQuery: String
    var dayKey: String
    var resultFoodIdsRaw: String
    var isMiss: Bool
    var createdAt: Date

    var resultFoodIds: [String] {
        get {
            resultFoodIdsRaw.split(separator: "|").map(String.init).filter { !$0.isEmpty }
        }
        set {
            resultFoodIdsRaw = newValue.joined(separator: "|")
        }
    }

    init(
        normalizedQuery: String,
        dayKey: String,
        resultFoodIds: [String],
        isMiss: Bool,
        createdAt: Date = .now
    ) {
        self.normalizedQuery = normalizedQuery
        self.dayKey = dayKey
        self.resultFoodIdsRaw = resultFoodIds.joined(separator: "|")
        self.isMiss = isMiss
        self.createdAt = createdAt
    }
}
