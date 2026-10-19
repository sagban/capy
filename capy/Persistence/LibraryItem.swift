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
        self.ingredients = ingredients
    }
}
