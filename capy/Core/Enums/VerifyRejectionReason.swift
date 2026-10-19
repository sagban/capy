import Foundation

enum VerifyRejectionReason: String, Equatable, Sendable {
    case caloriesExceedRemaining
    case proteinOutOfBand
    case carbsOutOfBand
    case fatOutOfBand
}
