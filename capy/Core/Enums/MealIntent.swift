import Foundation

enum MealIntent: String, Codable, Equatable, Sendable {
    case logMeal = "log_meal"
    case suggestMeal = "suggest_meal"
    case correctMeal = "correct_meal"
    case clarify
    case updatePreference = "update_preference"
    case updateMemory = "update_memory"
    case unknown
}
