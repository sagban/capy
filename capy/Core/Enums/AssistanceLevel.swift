import Foundation

enum AssistanceLevel: String, Codable, CaseIterable, Identifiable {
    case fullAssist
    case guided
    case quiet

    var id: String { rawValue }

    var title: String {
        switch self {
        case .fullAssist: "Full Assist"
        case .guided: "Guided"
        case .quiet: "Quiet"
        }
    }

    var subtitle: String {
        switch self {
        case .fullAssist: "Check-ins and a benefit after every log"
        case .guided: "One evening decision moment"
        case .quiet: "You talk; Capy stays quiet"
        }
    }
}
