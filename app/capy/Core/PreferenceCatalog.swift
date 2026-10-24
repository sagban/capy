import Foundation

protocol PreferenceChoice: Identifiable, Hashable where ID == String {
    var title: String { get }
    var emoji: String { get }
}

extension PreferenceChoice where Self: RawRepresentable, RawValue == String {
    var id: String { rawValue }
    var title: String { rawValue }
}

enum PreferenceCatalog {
    enum Diet: String, CaseIterable, PreferenceChoice {
        case omnivore = "Omnivore"
        case vegetarian = "Vegetarian"
        case vegan = "Vegan"
        case pescatarian = "Pescatarian"
        case flexitarian = "Flexitarian"
        case keto = "Keto"
        case lowCarb = "Low carb"
        case highProtein = "High protein"
        case mediterranean = "Mediterranean"
        case halal = "Halal"
        case kosher = "Kosher"
        case glutenFree = "Gluten-free"
        case dairyFree = "Dairy-free"

        var emoji: String {
            switch self {
            case .omnivore: "🍽️"
            case .vegetarian: "🥦"
            case .vegan: "🌱"
            case .pescatarian: "🐟"
            case .flexitarian: "🥙"
            case .keto: "🥑"
            case .lowCarb: "🥒"
            case .highProtein: "💪"
            case .mediterranean: "🍅"
            case .halal: "🌙"
            case .kosher: "✡️"
            case .glutenFree: "🌾"
            case .dairyFree: "🥛"
            }
        }
    }

    enum Like: String, CaseIterable, PreferenceChoice {
        case highFiber = "High fiber"
        case lowCalorie = "Low calorie"
        case quickMeals = "Quick meals"
        case mealPrep = "Meal prep friendly"
        case spicy = "Spicy"
        case mild = "Mild"
        case comfortFood = "Comfort food"
        case salads = "Salads"
        case soups = "Soups"
        case sandwiches = "Sandwiches"
        case riceBowls = "Rice bowls"
        case pasta = "Pasta"
        case eggs = "Eggs"
        case chicken = "Chicken"
        case fish = "Fish"
        case tofu = "Tofu"
        case yogurt = "Yogurt"
        case fruit = "Fruit"
        case vegetables = "Vegetables"

        var emoji: String {
            switch self {
            case .highFiber: "🥬"
            case .lowCalorie: "🍃"
            case .quickMeals: "⚡"
            case .mealPrep: "🥡"
            case .spicy: "🌶️"
            case .mild: "🧊"
            case .comfortFood: "🥧"
            case .salads: "🥗"
            case .soups: "🍜"
            case .sandwiches: "🥪"
            case .riceBowls: "🍛"
            case .pasta: "🍝"
            case .eggs: "🥚"
            case .chicken: "🍗"
            case .fish: "🐟"
            case .tofu: "🫘"
            case .yogurt: "🥣"
            case .fruit: "🍎"
            case .vegetables: "🥕"
            }
        }
    }

    enum Dislike: String, CaseIterable, PreferenceChoice {
        case mushrooms = "Mushrooms"
        case seafood = "Seafood"
        case olives = "Olives"
        case cilantro = "Cilantro"
        case blueCheese = "Blue cheese"
        case verySpicy = "Very spicy"
        case organMeats = "Organ meats"
        case processedMeats = "Processed meats"
        case sugaryDrinks = "Sugary drinks"
        case friedFood = "Fried food"

        var emoji: String {
            switch self {
            case .mushrooms: "🍄"
            case .seafood: "🦞"
            case .olives: "🫒"
            case .cilantro: "🌿"
            case .blueCheese: "🧀"
            case .verySpicy: "🥵"
            case .organMeats: "🥩"
            case .processedMeats: "🥓"
            case .sugaryDrinks: "🥤"
            case .friedFood: "🍟"
            }
        }
    }

    enum Allergy: String, CaseIterable, PreferenceChoice {
        case peanuts = "Peanuts"
        case treeNuts = "Tree nuts"
        case milk = "Milk"
        case eggs = "Eggs"
        case wheat = "Wheat"
        case soy = "Soy"
        case fish = "Fish"
        case shellfish = "Shellfish"
        case sesame = "Sesame"
        case gluten = "Gluten"

        var emoji: String {
            switch self {
            case .peanuts: "🥜"
            case .treeNuts: "🌰"
            case .milk: "🥛"
            case .eggs: "🥚"
            case .wheat: "🌾"
            case .soy: "🫛"
            case .fish: "🐟"
            case .shellfish: "🦐"
            case .sesame: "🌻"
            case .gluten: "🍞"
            }
        }
    }
}
