import Foundation

enum EnergyUnit: String, Codable, CaseIterable, Identifiable {
    case kcal
    case kilojoule

    var id: String { rawValue }

    var title: String {
        switch self {
        case .kcal: "Calories"
        case .kilojoule: "Kilojoules"
        }
    }

    var shortLabel: String {
        switch self {
        case .kcal: "cal"
        case .kilojoule: "kJ"
        }
    }

    var goalTitle: String {
        switch self {
        case .kcal: "Calories"
        case .kilojoule: "Energy"
        }
    }
}
