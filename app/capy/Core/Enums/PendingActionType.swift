import Foundation

enum PendingActionType: String, Codable, Equatable, Sendable {
    case clarifyPortion = "clarify_portion"
    case clarifyFood = "clarify_food"
    case confirmLog = "confirm_log"
    case confirmCorrection = "confirm_correction"
    case confirmDelete = "confirm_delete"
}
