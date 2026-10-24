import Foundation

/// Gemini Live prebuilt voices selectable for Capy Voice mode.
enum CapyVoice: String, Codable, CaseIterable, Identifiable {
    case puck = "Puck"
    case charon = "Charon"
    case kore = "Kore"
    case fenrir = "Fenrir"
    case aoede = "Aoede"
    case leda = "Leda"
    case orus = "Orus"
    case zephyr = "Zephyr"

    var id: String { rawValue }

    var title: String { rawValue }

    var subtitle: String {
        switch self {
        case .puck: "Upbeat and warm"
        case .charon: "Calm and steady"
        case .kore: "Clear and friendly"
        case .fenrir: "Deep and grounded"
        case .aoede: "Bright and expressive"
        case .leda: "Soft and conversational"
        case .orus: "Direct and balanced"
        case .zephyr: "Light and breezy"
        }
    }
}
