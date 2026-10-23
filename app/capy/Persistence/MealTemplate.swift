import Foundation
import SwiftData

@Model
final class MealTemplate {
    @Attribute(.unique) var id: String
    var name: String
    @Relationship(deleteRule: .cascade, inverse: \MealTemplateItem.template)
    var items: [MealTemplateItem]

    init(id: String, name: String, items: [MealTemplateItem] = []) {
        self.id = id
        self.name = name
        self.items = items
    }
}
