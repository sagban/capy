import Foundation
import SwiftData

@Model
final class MealType {
    var id: UUID
    var name: String
    var sortOrder: Int
    var isEnabled: Bool
    /// System defaults (Breakfast…Dinner) can be disabled but not deleted.
    var isSystem: Bool

    init(
        id: UUID = UUID(),
        name: String,
        sortOrder: Int,
        isEnabled: Bool = true,
        isSystem: Bool = false
    ) {
        self.id = id
        self.name = name
        self.sortOrder = sortOrder
        self.isEnabled = isEnabled
        self.isSystem = isSystem
    }
}
