import Foundation
import SwiftData

@Model
final class LibraryItem {
    var name: String
    var kindRaw: String
    var originRaw: String
    var detail: String
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    var createdAt: Date
    /// Stable id for nesting meals/recipes in other meals.
    var uuidString: String = UUID().uuidString
    /// JSON-encoded `[LibraryIngredientLine]` for recipes/meals; empty for simple foods.
    var ingredientsJSON: String = "[]"
    /// Catalog / OFF id when this food was imported (e.g. `off_3017620422003`); empty for hand-entered.
    var sourceFoodId: String = ""
    /// Grams represented by the stored calorie/PCF fields (one library serving).
    var servingGrams: Double = 100

    var kind: LibraryKind {
        get { LibraryKind(rawValue: kindRaw) ?? .meal }
        set { kindRaw = newValue.rawValue }
    }

    var origin: LibraryOrigin {
        get { LibraryOrigin(rawValue: originRaw) ?? .user }
        set { originRaw = newValue.rawValue }
    }

    var ingredients: [LibraryIngredientLine] {
        get {
            guard let data = ingredientsJSON.data(using: .utf8),
                  let decoded = try? JSONDecoder().decode([LibraryIngredientLine].self, from: data)
            else { return [] }
            return decoded
        }
        set {
            if let data = try? JSONEncoder().encode(newValue),
               let text = String(data: data, encoding: .utf8) {
                ingredientsJSON = text
            } else {
                ingredientsJSON = "[]"
            }
        }
    }

    init(
        name: String,
        kind: LibraryKind,
        origin: LibraryOrigin,
        detail: String = "",
        calories: Double = 0,
        proteinG: Double = 0,
        carbsG: Double = 0,
        fatG: Double = 0,
        ingredients: [LibraryIngredientLine] = [],
        sourceFoodId: String = "",
        servingGrams: Double = 100,
        createdAt: Date = .now
    ) {
        self.name = name
        self.kindRaw = kind.rawValue
        self.originRaw = origin.rawValue
        self.detail = detail
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
        self.createdAt = createdAt
        self.uuidString = UUID().uuidString
        self.ingredientsJSON = "[]"
        self.sourceFoodId = sourceFoodId
        self.servingGrams = max(servingGrams, 1)
        self.ingredients = ingredients
    }

    /// Upsert a simple food from an Open Food Facts barcode hit (macros = 1 serving).
    @discardableResult
    static func upsertFromBarcodeHit(
        _ hit: BarcodeLookupHit,
        perServing: MacroTotals,
        in context: ModelContext
    ) -> LibraryItem {
        let foodId = hit.foodId
        let detail: String = {
            if let brand = hit.brand, !brand.isEmpty { return brand }
            if let label = hit.servingLabel, !label.isEmpty { return label }
            return "Open Food Facts"
        }()
        let existing: LibraryItem? = {
            guard !foodId.isEmpty else { return nil }
            var descriptor = FetchDescriptor<LibraryItem>(
                predicate: #Predicate { $0.sourceFoodId == foodId }
            )
            descriptor.fetchLimit = 1
            return try? context.fetch(descriptor).first
        }()

        if let existing {
            existing.name = hit.displayName
            existing.detail = detail
            existing.calories = perServing.calories
            existing.proteinG = perServing.proteinG
            existing.carbsG = perServing.carbsG
            existing.fatG = perServing.fatG
            existing.kind = .food
            return existing
        }

        let item = LibraryItem(
            name: hit.displayName,
            kind: .food,
            origin: .user,
            detail: detail,
            calories: perServing.calories,
            proteinG: perServing.proteinG,
            carbsG: perServing.carbsG,
            fatG: perServing.fatG,
            sourceFoodId: foodId
        )
        context.insert(item)
        return item
    }

    /// Refresh name/macros for a barcode-imported food after the user confirms a log.
    static func updateFromBarcodeLog(
        foodId: String,
        name: String,
        detail: String,
        perServing: MacroTotals,
        in context: ModelContext
    ) {
        guard foodId.hasPrefix("off_"), !foodId.isEmpty else { return }
        var descriptor = FetchDescriptor<LibraryItem>(
            predicate: #Predicate { $0.sourceFoodId == foodId }
        )
        descriptor.fetchLimit = 1
        guard let existing = try? context.fetch(descriptor).first else { return }
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty {
            existing.name = trimmed
        }
        if !detail.isEmpty {
            existing.detail = detail
        }
        existing.calories = perServing.calories
        existing.proteinG = perServing.proteinG
        existing.carbsG = perServing.carbsG
        existing.fatG = perServing.fatG
    }

    /// Save a Capy-confirmed web/estimate food into Library (AI-generated) for reuse.
    @discardableResult
    static func upsertFromAcceptedAgentLine(
        name: String,
        foodId: String,
        grams: Double,
        per100g: MacroTotals,
        source: String,
        citationUrl: String?,
        portionLabel: String?,
        in context: ModelContext
    ) -> LibraryItem? {
        let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedName.isEmpty, grams > 0 else { return nil }
        let sourceKey = source.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let isAICited = sourceKey == "web" || sourceKey == "estimate"
            || foodId.hasPrefix("web_") || foodId.hasPrefix("est_")
        guard isAICited else { return nil }

        let portion = MacroMath.scale(per100g: per100g, grams: grams)
        let detail: String = {
            if let portionLabel, !portionLabel.isEmpty { return portionLabel }
            if let citationUrl, !citationUrl.isEmpty { return citationUrl }
            return sourceKey == "web" ? "web" : "AI estimate"
        }()
        let key = foodId.trimmingCharacters(in: .whitespacesAndNewlines)

        let existing: LibraryItem? = {
            guard !key.isEmpty else { return nil }
            var descriptor = FetchDescriptor<LibraryItem>(
                predicate: #Predicate { $0.sourceFoodId == key }
            )
            descriptor.fetchLimit = 1
            return try? context.fetch(descriptor).first
        }()

        if let existing {
            existing.name = trimmedName
            existing.detail = detail
            existing.calories = portion.calories
            existing.proteinG = portion.proteinG
            existing.carbsG = portion.carbsG
            existing.fatG = portion.fatG
            existing.servingGrams = grams
            existing.kind = .food
            existing.origin = .aiGenerated
            if existing.sourceFoodId.isEmpty {
                existing.sourceFoodId = key
            }
            return existing
        }

        let item = LibraryItem(
            name: trimmedName,
            kind: .food,
            origin: .aiGenerated,
            detail: detail,
            calories: portion.calories,
            proteinG: portion.proteinG,
            carbsG: portion.carbsG,
            fatG: portion.fatG,
            sourceFoodId: key,
            servingGrams: grams
        )
        context.insert(item)
        return item
    }
}
