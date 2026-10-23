import Foundation

enum WeekStartPreference: String, Codable, CaseIterable, Identifiable {
    case system
    case sunday
    case monday

    var id: String { rawValue }

    var title: String {
        switch self {
        case .system: "System"
        case .sunday: "Sunday"
        case .monday: "Monday"
        }
    }

    /// Calendar weekday (1 = Sunday … 7 = Saturday), or nil to use device default.
    var calendarWeekday: Int? {
        switch self {
        case .system: nil
        case .sunday: 1
        case .monday: 2
        }
    }
}
