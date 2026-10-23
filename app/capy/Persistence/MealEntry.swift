import Foundation
import SwiftData

@Model
final class MealEntry {
    var timestamp: Date
    var dayKey: String
    var mealSlot: String?
    var originalUserText: String?
    var confirmed: Bool
    /// Stable id sent to the agent so repeat and correct target this entry.
    var uuid: UUID = UUID()
    @Relationship(deleteRule: .cascade, inverse: \MealEntryItem.entry)
    var items: [MealEntryItem]

    init(
        timestamp: Date = .now,
        dayKey: String,
        mealSlot: String? = nil,
        originalUserText: String? = nil,
        confirmed: Bool = true,
        items: [MealEntryItem] = []
    ) {
        self.timestamp = timestamp
        self.dayKey = dayKey
        self.mealSlot = mealSlot
        self.originalUserText = originalUserText
        self.confirmed = confirmed
        self.items = items
    }

    var calories: Double { items.reduce(0) { $0 + $1.calories } }
    var proteinG: Double { items.reduce(0) { $0 + $1.proteinG } }
    var carbsG: Double { items.reduce(0) { $0 + $1.carbsG } }
    var fatG: Double { items.reduce(0) { $0 + $1.fatG } }
}
