import Foundation

enum FoodMassUnit: String, Codable, CaseIterable, Identifiable {
    case gram
    case ounce

    var id: String { rawValue }

    var title: String {
        switch self {
        case .gram: "Grams"
        case .ounce: "Ounces"
        }
    }

    var shortLabel: String {
        switch self {
        case .gram: "g"
        case .ounce: "oz"
        }
    }

    /// Default portion picker unit from settings weight preference.
    var defaultPortionUnit: PortionUnit {
        switch self {
        case .gram: .gram
        case .ounce: .ounce
        }
    }
}
