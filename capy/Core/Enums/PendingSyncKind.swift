import Foundation

enum PendingSyncKind: String, Codable {
    case logMeal
    case deleteMeal
    case patchProfile
}
