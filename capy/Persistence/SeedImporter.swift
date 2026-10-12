import Foundation
import SwiftData

enum SeedImporter {
    private static let bundleResource = "SeedFoods"
    private static let importedFlagKey = "capy.seedCatalog.version"

    struct SeedFile: Decodable {
        let version: Int
        let foods: [SeedFood]
        let composites: [SeedComposite]
        let templates: [SeedTemplate]
    }

    struct SeedFood: Decodable {
        let id: String
        let name: String
        let family: String
        let per100g: SeedMacros
        let aliases: [String]?
        let usdaFdcId: Int?
        let source: String?
    }

    struct SeedMacros: Decodable {
        let calories: Double
        let proteinG: Double
        let carbsG: Double
        let fatG: Double

        var asTotals: MacroTotals {
            MacroTotals(calories: calories, proteinG: proteinG, carbsG: carbsG, fatG: fatG)
        }
    }

    struct SeedComposite: Decodable {
        let id: String
        let name: String
        let isComposite: Bool?
        let components: [SeedComponent]
    }

    struct SeedComponent: Decodable {
        let foodId: String
        let grams: Double
    }

    struct SeedTemplate: Decodable {
        let id: String
        let name: String
        let items: [SeedComponent]
    }

    @discardableResult
    static func importIfNeeded(into context: ModelContext, bundle: Bundle = .main) throws -> Bool {
        guard let url = bundle.url(forResource: bundleResource, withExtension: "json") else {
            throw SeedImportError.missingBundleResource
        }
        let data = try Data(contentsOf: url)
        let file = try JSONDecoder().decode(SeedFile.self, from: data)
        let flag = "\(importedFlagKey).\(file.version)"
        if UserDefaults.standard.bool(forKey: flag) {
            let existing = try context.fetch(FetchDescriptor<Food>())
            if !existing.isEmpty { return false }
        }
        try importAll(file: file, into: context)
        UserDefaults.standard.set(true, forKey: flag)
        return true
    }

    /// Idempotent upsert by food/template id.
    static func importAll(file: SeedFile, into context: ModelContext) throws {
        var foodById: [String: Food] = [:]
        for seed in file.foods {
            let source: FoodSource = {
                switch seed.source {
                case "overlay", "seed": return .seed
                case "usda_foundation", "usda_sr_legacy", "usda": return .usda
                default: return seed.id.hasPrefix("usda_") ? .usda : .seed
                }
            }()
            let food = upsertFood(
                id: seed.id,
                name: seed.name,
                aliases: seed.aliases ?? [],
                family: seed.family,
                per100g: seed.per100g.asTotals,
                isComposite: false,
                source: source,
                usdaFdcId: seed.usdaFdcId,
                into: context
            )
            foodById[seed.id] = food
        }

        for composite in file.composites {
            var totals = MacroTotals.zero
            var totalGrams = 0.0
            for component in composite.components {
                guard let base = foodById[component.foodId] ?? fetchFood(id: component.foodId, in: context) else {
                    continue
                }
                totals = totals + MacroMath.scale(per100g: base.per100g, grams: component.grams)
                totalGrams += component.grams
            }
            let per100: MacroTotals
            if totalGrams > 0 {
                let factor = 100.0 / totalGrams
                per100 = MacroTotals(
                    calories: totals.calories * factor,
                    proteinG: totals.proteinG * factor,
                    carbsG: totals.carbsG * factor,
                    fatG: totals.fatG * factor
                )
            } else {
                per100 = .zero
            }
            let food = upsertFood(
                id: composite.id,
                name: composite.name,
                aliases: [],
                family: "composite",
                per100g: per100,
                isComposite: true,
                source: .seed,
                into: context
            )
            foodById[composite.id] = food
        }

        for template in file.templates {
            upsertTemplate(template, into: context)
        }
        try context.save()
    }

    private static func upsertFood(
        id: String,
        name: String,
        aliases: [String],
        family: String,
        per100g: MacroTotals,
        isComposite: Bool,
        source: FoodSource = .seed,
        usdaFdcId: Int? = nil,
        into context: ModelContext
    ) -> Food {
        if let existing = fetchFood(id: id, in: context) {
            existing.canonicalName = name
            existing.aliases = aliases
            existing.ingredientFamily = family
            existing.caloriesPer100g = per100g.calories
            existing.proteinGPer100g = per100g.proteinG
            existing.carbsGPer100g = per100g.carbsG
            existing.fatGPer100g = per100g.fatG
            existing.isComposite = isComposite
            existing.source = source
            if let usdaFdcId { existing.usdaFdcId = usdaFdcId }
            existing.cachedAt = .now
            return existing
        }
        let food = Food(
            id: id,
            canonicalName: name,
            aliases: aliases,
            source: source,
            usdaFdcId: usdaFdcId,
            per100g: per100g,
            ingredientFamily: family,
            isComposite: isComposite
        )
        context.insert(food)
        return food
    }

    private static func upsertTemplate(_ template: SeedTemplate, into context: ModelContext) {
        if let existing = fetchTemplate(id: template.id, in: context) {
            for item in existing.items {
                context.delete(item)
            }
            existing.name = template.name
            existing.items = template.items.map { MealTemplateItem(foodId: $0.foodId, grams: $0.grams) }
            return
        }
        let model = MealTemplate(
            id: template.id,
            name: template.name,
            items: template.items.map { MealTemplateItem(foodId: $0.foodId, grams: $0.grams) }
        )
        context.insert(model)
    }

    private static func fetchFood(id: String, in context: ModelContext) -> Food? {
        var descriptor = FetchDescriptor<Food>(predicate: #Predicate { $0.id == id })
        descriptor.fetchLimit = 1
        return try? context.fetch(descriptor).first
    }

    private static func fetchTemplate(id: String, in context: ModelContext) -> MealTemplate? {
        var descriptor = FetchDescriptor<MealTemplate>(predicate: #Predicate { $0.id == id })
        descriptor.fetchLimit = 1
        return try? context.fetch(descriptor).first
    }

    static func searchFoods(query: String, in context: ModelContext, limit: Int = 30) -> [Food] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let all = (try? context.fetch(FetchDescriptor<Food>(sortBy: [SortDescriptor(\.canonicalName)]))) ?? []
        guard !q.isEmpty else { return Array(all.prefix(limit)) }
        return Array(
            all.filter { food in
                food.canonicalName.lowercased().contains(q)
                    || food.aliases.contains(where: { $0.lowercased().contains(q) })
                    || food.ingredientFamily.lowercased().contains(q)
            }
            .prefix(limit)
        )
    }
}

enum SeedImportError: Error {
    case missingBundleResource
}
