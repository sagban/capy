import Foundation

enum MeasurementSystem: String, Codable, CaseIterable, Identifiable {
    case metric
    case imperial

    var id: String { rawValue }

    var title: String {
        switch self {
        case .metric: "Metric"
        case .imperial: "Imperial"
        }
    }

    var foodMass: FoodMassUnit {
        switch self {
        case .metric: .gram
        case .imperial: .ounce
        }
    }

    var bodyMass: BodyMassUnit {
        switch self {
        case .metric: .kilogram
        case .imperial: .pound
        }
    }

    static func matching(food: FoodMassUnit, body: BodyMassUnit) -> MeasurementSystem? {
        if food == .gram && body == .kilogram { return .metric }
        if food == .ounce && body == .pound { return .imperial }
        return nil
    }
}
