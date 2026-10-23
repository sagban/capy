import Foundation
import SwiftData

enum SeedImporter {
    private static let bundleResource = "SeedFoods"
    /// Must match `version` in SeedFoods.json (catalog build script bumps both).
    static let bundledCatalogVersion = 3
    private static let importedVersionKey = "capy.seedCatalog.importedVersion"
    private static let legacyFlagPrefix = "capy.seedCatalog.version"

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
        let servingGrams: Double?
        let servingLabel: String?
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

    /// Cheap readiness check — no JSON decode, at most one Food row.
    static func isCatalogReady(in context: ModelContext) -> Bool {
        let imported = UserDefaults.standard.integer(forKey: importedVersionKey)
        let legacyReady = UserDefaults.standard.bool(
            forKey: "\(legacyFlagPrefix).\(bundledCatalogVersion)"
        )
        guard imported >= bundledCatalogVersion || legacyReady else { return false }
        var descriptor = FetchDescriptor<Food>()
        descriptor.fetchLimit = 1
        return (try? context.fetch(descriptor))?.first != nil
    }

    /// Background import for app launch. No-ops when catalog already ready.
    static func importInBackground(container: ModelContainer, bundle: Bundle = .main) async {
        let probe = ModelContext(container)
        if isCatalogReady(in: probe) { return }
        await Task.detached(priority: .userInitiated) {
            let context = ModelContext(container)
            try? importIfNeeded(into: context, bundle: bundle)
        }.value
    }

    @discardableResult
    static func importIfNeeded(into context: ModelContext, bundle: Bundle = .main) throws -> Bool {
        if isCatalogReady(in: context) { return false }
        guard let url = bundle.url(forResource: bundleResource, withExtension: "json") else {
            throw SeedImportError.missingBundleResource
        }
        let data = try Data(contentsOf: url)
        let file = try JSONDecoder().decode(SeedFile.self, from: data)
        try importAll(file: file, into: context)
        UserDefaults.standard.set(file.version, forKey: importedVersionKey)
        UserDefaults.standard.set(true, forKey: "\(legacyFlagPrefix).\(file.version)")
        return true
    }

    /// Idempotent upsert by food/template id.
    static func importAll(file: SeedFile, into context: ModelContext) throws {
        let existingFoods = (try? context.fetch(FetchDescriptor<Food>())) ?? []
        var foodById = Dictionary(uniqueKeysWithValues: existingFoods.map { ($0.id, $0) })

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
                servingGrams: seed.servingGrams ?? 0,
                servingLabel: seed.servingLabel ?? "",
                isComposite: false,
                source: source,
                usdaFdcId: seed.usdaFdcId,
                existing: foodById[seed.id],
                into: context
            )
            foodById[seed.id] = food
        }

        for composite in file.composites {
            var totals = MacroTotals.zero
            var totalGrams = 0.0
            for component in composite.components {
                guard let base = foodById[component.foodId] else { continue }
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
                servingGrams: totalGrams > 0 ? totalGrams : 0,
                servingLabel: totalGrams > 0 ? "1 bowl" : "",
                isComposite: true,
                source: .seed,
                existing: foodById[composite.id],
                into: context
            )
            foodById[composite.id] = food
        }

        let existingTemplates = (try? context.fetch(FetchDescriptor<MealTemplate>())) ?? []
        let templateById = Dictionary(uniqueKeysWithValues: existingTemplates.map { ($0.id, $0) })
        for template in file.templates {
            upsertTemplate(template, existing: templateById[template.id], into: context)
        }
        try context.save()
    }

    private static func upsertFood(
        id: String,
        name: String,
        aliases: [String],
        family: String,
        per100g: MacroTotals,
        servingGrams: Double = 0,
        servingLabel: String = "",
        isComposite: Bool,
        source: FoodSource = .seed,
        usdaFdcId: Int? = nil,
        existing: Food?,
        into context: ModelContext
    ) -> Food {
        if let existing {
            existing.canonicalName = name
            existing.aliases = aliases
            existing.ingredientFamily = family
            existing.caloriesPer100g = per100g.calories
            existing.proteinGPer100g = per100g.proteinG
            existing.carbsGPer100g = per100g.carbsG
            existing.fatGPer100g = per100g.fatG
            existing.servingGrams = servingGrams
            existing.servingLabel = servingLabel
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
            servingGrams: servingGrams,
            servingLabel: servingLabel,
            ingredientFamily: family,
            isComposite: isComposite
        )
        context.insert(food)
        return food
    }

    private static func upsertTemplate(
        _ template: SeedTemplate,
        existing: MealTemplate?,
        into context: ModelContext
    ) {
        if let existing {
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

    static func searchFoods(query: String, in context: ModelContext, limit: Int = 30) -> [Food] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        // Empty query: no A→Z dump — Manual Log uses recent/meal suggestions instead.
        if q.isEmpty {
            return []
        }
        let needle = q.lowercased()
        // Short queries: avoid substring traps ("hi" ⊂ "chicken" / "white").
        // Pull a wider pool, then rank staples above babyfood / brand noise.
        let candidates: [Food]
        if needle.count < 3 {
            var descriptor = FetchDescriptor<Food>()
            descriptor.fetchLimit = 400
            let pool = (try? context.fetch(descriptor)) ?? []
            candidates = pool.filter { food in
                FoodSearchRanker.shortQueryMatches(
                    query: needle,
                    name: food.canonicalName,
                    aliases: food.aliases
                )
            }
        } else {
            let predicate = #Predicate<Food> { food in
                food.canonicalName.localizedStandardContains(needle)
                    || food.aliasesRaw.localizedStandardContains(needle)
                    || food.ingredientFamily.localizedStandardContains(needle)
            }
            var descriptor = FetchDescriptor<Food>(predicate: predicate)
            descriptor.fetchLimit = max(limit * 12, 200)
            candidates = (try? context.fetch(descriptor)) ?? []
        }
        return FoodSearchRanker.ranked(
            candidates,
            query: q,
            name: \.canonicalName,
            aliases: \.aliases,
            family: \.ingredientFamily,
            foodId: \.id,
            limit: limit
        )
    }
}

enum SeedImportError: Error {
    case missingBundleResource
}
