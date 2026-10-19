import Foundation
import SwiftData

enum MealTypeCatalog {
    static let defaults: [(name: String, order: Int)] = [
        ("Breakfast", 0),
        ("Lunch", 1),
        ("Snacks", 2),
        ("Dinner", 3),
    ]

    static func seedIfNeeded(in context: ModelContext) {
        let descriptor = FetchDescriptor<MealType>()
        let existing = (try? context.fetch(descriptor)) ?? []
        guard existing.isEmpty else { return }
        for item in defaults {
            context.insert(
                MealType(name: item.name, sortOrder: item.order, isEnabled: true, isSystem: true)
            )
        }
    }

    /// Best-effort slot from clock time among currently enabled types.
    static func suggestedName(from enabled: [MealType], date: Date = .now) -> String? {
        guard !enabled.isEmpty else { return nil }
        let hour = Calendar.current.component(.hour, from: date)
        let preferred: String = switch hour {
        case 4..<11: "Breakfast"
        case 11..<15: "Lunch"
        case 15..<17: "Snacks"
        case 17..<22: "Dinner"
        default: "Snacks"
        }
        if let match = enabled.first(where: { $0.name == preferred }) {
            return match.name
        }
        return enabled.first?.name
    }
}
