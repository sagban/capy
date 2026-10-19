import Foundation

/// What a suggestion was built for: a calorie ceiling and optional protein floor
/// (stated, else the slot's typical meal, else weighted slot defaults on what's left).
/// Not the whole day's remainder. There is no calorie floor.
struct SuggestionBudget: Equatable, Sendable {
    var calories: Double
    var proteinG: Double?
    var carbsG: Double?
    var fatG: Double?
}
