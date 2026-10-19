import Foundation
import SwiftData

@Model
final class MealTemplateItem {
    var foodId: String
    var grams: Double
    var template: MealTemplate?

    init(foodId: String, grams: Double) {
        self.foodId = foodId
        self.grams = grams
    }
}
