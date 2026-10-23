import Foundation

enum FoodSource: String, Codable, CaseIterable {
    case seed
    case usda
    case user
    case aiGenerated
}
