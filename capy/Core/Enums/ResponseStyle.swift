import Foundation

/// How Capy phrases replies (server maps to model sampling; not shown as temperature in UI).
enum ResponseStyle: String, Codable, CaseIterable, Identifiable {
    case precise
    case balanced
    case creative

    var id: String { rawValue }

    var title: String {
        switch self {
        case .precise: "Precise"
        case .balanced: "Balanced"
        case .creative: "Creative"
        }
    }

    var subtitle: String {
        switch self {
        case .precise: "Sticks to facts and steady estimates"
        case .balanced: "Natural replies with room to rephrase"
        case .creative: "More flexible wording and ideas"
        }
    }
}
