import Foundation

/// One line in a user recipe or meal (snapshot so renames don’t break history).
/// Always stores **grams** + true per-100g macros; `servingGrams` is the 1-serving reference
/// for the portion unit picker (same as Manual Log).
struct LibraryIngredientLine: Codable, Hashable, Identifiable {
    var id: String
    var foodId: String
    var name: String
    /// Quantity in grams (source of truth).
    var grams: Double
    /// Grams in one “serving” for `PortionUnit.serving`.
    var servingGrams: Double
    var caloriesPer100g: Double
    var proteinGPer100g: Double
    var carbsGPer100g: Double
    var fatGPer100g: Double
    var source: LibraryIngredientSource
    /// Library kind when `source == .libraryItem` (`meal` / `recipe` / `food`).
    var libraryKindRaw: String

    var libraryKind: LibraryKind? {
        LibraryKind(rawValue: libraryKindRaw)
    }

    var per100g: MacroTotals {
        MacroTotals(
            calories: caloriesPer100g,
            proteinG: proteinGPer100g,
            carbsG: carbsGPer100g,
            fatG: fatGPer100g
        )
    }

    var macros: MacroTotals {
        MacroMath.scale(per100g: per100g, grams: grams)
    }

    static func from(food: Food, grams: Double, servingGrams: Double) -> LibraryIngredientLine {
        LibraryIngredientLine(
            id: UUID().uuidString,
            foodId: food.id,
            name: food.canonicalName,
            grams: grams,
            servingGrams: max(servingGrams, 1),
            caloriesPer100g: food.caloriesPer100g,
            proteinGPer100g: food.proteinGPer100g,
            carbsGPer100g: food.carbsGPer100g,
            fatGPer100g: food.fatGPer100g,
            source: .catalogFood,
            libraryKindRaw: ""
        )
    }

    /// Library recipe/food/meal as one serving (macros snapped; virtual weight for unit picker).
    static func from(libraryItem item: LibraryItem, servings: Double = 1) -> LibraryIngredientLine {
        let servingG: Double = {
            let fromParts = item.ingredients
                .filter { $0.source == .catalogFood || $0.servingGrams > 0 }
                .map(\.grams)
                .reduce(0, +)
            return fromParts > 0 ? fromParts : 100
        }()
        let perServing = MacroTotals(
            calories: item.calories,
            proteinG: item.proteinG,
            carbsG: item.carbsG,
            fatG: item.fatG
        )
        let factor = 100.0 / servingG
        return LibraryIngredientLine(
            id: UUID().uuidString,
            foodId: item.uuidString,
            name: item.name,
            grams: servingG * servings,
            servingGrams: servingG,
            caloriesPer100g: perServing.calories * factor,
            proteinGPer100g: perServing.proteinG * factor,
            carbsGPer100g: perServing.carbsG * factor,
            fatGPer100g: perServing.fatG * factor,
            source: .libraryItem,
            libraryKindRaw: item.kind.rawValue
        )
    }

    static func totals(_ lines: [LibraryIngredientLine]) -> MacroTotals {
        lines.reduce(.zero) { $0 + $1.macros }
    }

    enum CodingKeys: String, CodingKey {
        case id, foodId, name, grams, servingGrams
        case caloriesPer100g, proteinGPer100g, carbsGPer100g, fatGPer100g
        case unit, source, libraryKindRaw
    }

    init(
        id: String,
        foodId: String,
        name: String,
        grams: Double,
        servingGrams: Double,
        caloriesPer100g: Double,
        proteinGPer100g: Double,
        carbsGPer100g: Double,
        fatGPer100g: Double,
        source: LibraryIngredientSource = .catalogFood,
        libraryKindRaw: String = ""
    ) {
        self.id = id
        self.foodId = foodId
        self.name = name
        self.grams = grams
        self.servingGrams = max(servingGrams, 1)
        self.caloriesPer100g = caloriesPer100g
        self.proteinGPer100g = proteinGPer100g
        self.carbsGPer100g = carbsGPer100g
        self.fatGPer100g = fatGPer100g
        self.source = source
        self.libraryKindRaw = libraryKindRaw
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        foodId = try c.decode(String.self, forKey: .foodId)
        name = try c.decode(String.self, forKey: .name)
        var decodedGrams = try c.decode(Double.self, forKey: .grams)
        let decodedCal = try c.decode(Double.self, forKey: .caloriesPer100g)
        let decodedP = try c.decode(Double.self, forKey: .proteinGPer100g)
        let decodedC = try c.decode(Double.self, forKey: .carbsGPer100g)
        let decodedF = try c.decode(Double.self, forKey: .fatGPer100g)
        source = try c.decodeIfPresent(LibraryIngredientSource.self, forKey: .source) ?? .catalogFood
        libraryKindRaw = try c.decodeIfPresent(String.self, forKey: .libraryKindRaw) ?? ""
        // Legacy: unit == serving meant `grams` was a serving count and *Per100g were per-serving.
        let legacyUnit = try c.decodeIfPresent(String.self, forKey: .unit)
        if legacyUnit == "serving" {
            let servings = max(decodedGrams, 0)
            let servingG = 100.0
            decodedGrams = servingG * servings
            servingGrams = servingG
        } else {
            servingGrams = try c.decodeIfPresent(Double.self, forKey: .servingGrams) ?? max(decodedGrams, 1)
        }
        grams = decodedGrams
        caloriesPer100g = decodedCal
        proteinGPer100g = decodedP
        carbsGPer100g = decodedC
        fatGPer100g = decodedF
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(foodId, forKey: .foodId)
        try c.encode(name, forKey: .name)
        try c.encode(grams, forKey: .grams)
        try c.encode(servingGrams, forKey: .servingGrams)
        try c.encode(caloriesPer100g, forKey: .caloriesPer100g)
        try c.encode(proteinGPer100g, forKey: .proteinGPer100g)
        try c.encode(carbsGPer100g, forKey: .carbsGPer100g)
        try c.encode(fatGPer100g, forKey: .fatGPer100g)
        try c.encode(source, forKey: .source)
        try c.encode(libraryKindRaw, forKey: .libraryKindRaw)
    }
}
