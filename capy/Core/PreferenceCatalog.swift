import Foundation

enum PreferenceCatalog {
    static let diets = [
        "Omnivore",
        "Vegetarian",
        "Vegan",
        "Pescatarian",
        "Flexitarian",
        "Keto",
        "Low carb",
        "High protein",
        "Mediterranean",
        "Halal",
        "Kosher",
        "Gluten-free",
        "Dairy-free",
    ]

    static let likes = [
        "High protein",
        "High fiber",
        "Low calorie",
        "Quick meals",
        "Meal prep friendly",
        "Spicy",
        "Mild",
        "Comfort food",
        "Salads",
        "Soups",
        "Sandwiches",
        "Rice bowls",
        "Pasta",
        "Eggs",
        "Chicken",
        "Fish",
        "Tofu",
        "Yogurt",
        "Fruit",
        "Vegetables",
    ]

    static let dislikes = [
        "Mushrooms",
        "Seafood",
        "Shellfish",
        "Olives",
        "Cilantro",
        "Blue cheese",
        "Very spicy",
        "Organ meats",
        "Processed meats",
        "Sugary drinks",
        "Fried food",
    ]

    static let allergies = [
        "Peanuts",
        "Tree nuts",
        "Milk",
        "Eggs",
        "Wheat",
        "Soy",
        "Fish",
        "Shellfish",
        "Sesame",
        "Gluten",
    ]

    static func options(for kind: PreferenceKind) -> [String] {
        switch kind {
        case .diet: diets
        case .like: likes
        case .dislike: dislikes
        case .allergy: allergies
        }
    }
}
