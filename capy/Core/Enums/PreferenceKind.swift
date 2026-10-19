import Foundation

enum PreferenceKind: String, Codable, CaseIterable, Identifiable {
    case like
    case dislike
    case allergy
    case diet

    var id: String { rawValue }

    var title: String {
        switch self {
        case .like: "Preference"
        case .dislike: "Dislike"
        case .allergy: "Allergy"
        case .diet: "Diet"
        }
    }
}
