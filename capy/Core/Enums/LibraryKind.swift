import Foundation

enum LibraryKind: String, Codable, CaseIterable, Identifiable {
    case meal
    case recipe
    case food

    var id: String { rawValue }

    var title: String {
        switch self {
        case .meal: "Meals"
        case .recipe: "Recipes"
        case .food: "Foods"
        }
    }
}
