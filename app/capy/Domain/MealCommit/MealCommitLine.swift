import Foundation

/// One food line ready to commit to the diary (Capy confirm or Manual Log).
struct MealCommitLine: Equatable, Sendable {
    var name: String
    var foodId: String
    var grams: Double
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    var family: String
    var source: String
    /// True per-100g density when known (agent confirm); nil for manual drafts.
    var per100g: MacroTotals?
    var citationUrl: String?
    var portionLabel: String?
    var entryId: String?
    var itemIndex: Int?

    var macros: MacroTotals {
        if let per100g {
            return MacroMath.scale(per100g: per100g, grams: grams)
        }
        return MacroTotals(
            calories: calories,
            proteinG: proteinG,
            carbsG: carbsG,
            fatG: fatG
        )
    }

    init(
        name: String,
        foodId: String,
        grams: Double,
        calories: Double,
        proteinG: Double,
        carbsG: Double,
        fatG: Double,
        family: String = "",
        source: String = "",
        per100g: MacroTotals? = nil,
        citationUrl: String? = nil,
        portionLabel: String? = nil,
        entryId: String? = nil,
        itemIndex: Int? = nil
    ) {
        self.name = name
        self.foodId = foodId
        self.grams = grams
        self.calories = calories
        self.proteinG = proteinG
        self.carbsG = carbsG
        self.fatG = fatG
        self.family = family
        self.source = source
        self.per100g = per100g
        self.citationUrl = citationUrl
        self.portionLabel = portionLabel
        self.entryId = entryId
        self.itemIndex = itemIndex
    }

    init(confirmLine line: ConfirmLine) {
        self.init(
            name: line.name,
            foodId: line.foodId,
            grams: line.grams,
            calories: line.macros.calories,
            proteinG: line.macros.proteinG,
            carbsG: line.macros.carbsG,
            fatG: line.macros.fatG,
            family: line.family,
            source: line.source,
            per100g: line.per100g,
            citationUrl: line.citationUrl,
            portionLabel: line.portionLabel,
            entryId: line.entryId,
            itemIndex: line.itemIndex
        )
    }
}
