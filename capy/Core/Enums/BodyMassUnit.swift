import Foundation

enum BodyMassUnit: String, Codable, CaseIterable, Identifiable {
    case kilogram
    case pound

    var id: String { rawValue }

    var title: String {
        switch self {
        case .kilogram: "Kilograms"
        case .pound: "Pounds"
        }
    }

    var shortLabel: String {
        switch self {
        case .kilogram: "kg"
        case .pound: "lb"
        }
    }
}
