import Foundation

/// Source of a composition line (catalog staple vs library item).
enum LibraryIngredientSource: String, Codable, Hashable {
    case catalogFood
    case libraryItem
}
