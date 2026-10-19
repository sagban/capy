import Foundation

enum VerifyOutcome: Equatable, Sendable {
    case accepted(MacroTotals)
    case rejected(reason: VerifyRejectionReason, computed: MacroTotals)
    case abstain(reasons: [VerifyRejectionReason])
}
