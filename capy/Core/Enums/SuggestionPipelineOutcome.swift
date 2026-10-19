import Foundation

enum SuggestionPipelineOutcome: Equatable, Sendable {
    case accepted(PipelineCandidate)
    case abstain(reasons: [VerifyRejectionReason])
}
