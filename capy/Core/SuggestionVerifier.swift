import Foundation

enum VerifyRejectionReason: String, Equatable, Sendable {
    case caloriesExceedRemaining
    case proteinOutOfBand
    case carbsOutOfBand
    case fatOutOfBand
}

enum VerifyOutcome: Equatable, Sendable {
    case accepted(MacroTotals)
    case rejected(reason: VerifyRejectionReason, computed: MacroTotals)
    case abstain(reasons: [VerifyRejectionReason])
}

/// Deterministic suggestion verifier. LLM never supplies trusted macros.
enum SuggestionVerifier {
    /// Each macro must land within ±`band` of remaining (default 10%).
    /// Calories must be ≤ remaining calories.
    static let defaultBand = 0.10
    static let maxRetries = 2

    static func verify(
        proposed: MacroTotals,
        remaining: MacroTotals,
        band: Double = defaultBand
    ) -> VerifyOutcome {
        if proposed.calories > remaining.calories {
            return .rejected(reason: .caloriesExceedRemaining, computed: proposed)
        }
        if !withinBand(proposed.proteinG, target: remaining.proteinG, band: band) {
            return .rejected(reason: .proteinOutOfBand, computed: proposed)
        }
        if !withinBand(proposed.carbsG, target: remaining.carbsG, band: band) {
            return .rejected(reason: .carbsOutOfBand, computed: proposed)
        }
        if !withinBand(proposed.fatG, target: remaining.fatG, band: band) {
            return .rejected(reason: .fatOutOfBand, computed: proposed)
        }
        return .accepted(proposed)
    }

    /// Try proposals in order; after `maxRetries` failures (attempts = 1 + maxRetries), abstain.
    static func verifyWithRetries(
        proposals: [MacroTotals],
        remaining: MacroTotals,
        band: Double = defaultBand,
        maxRetries: Int = maxRetries
    ) -> VerifyOutcome {
        var reasons: [VerifyRejectionReason] = []
        let maxAttempts = 1 + maxRetries
        for (index, proposal) in proposals.prefix(maxAttempts).enumerated() {
            switch verify(proposed: proposal, remaining: remaining, band: band) {
            case .accepted(let totals):
                return .accepted(totals)
            case .rejected(let reason, _):
                reasons.append(reason)
                if index + 1 >= maxAttempts {
                    return .abstain(reasons: reasons)
                }
            case .abstain(let already):
                return .abstain(reasons: already)
            }
        }
        return .abstain(reasons: reasons.isEmpty ? [.caloriesExceedRemaining] : reasons)
    }

    static func withinBand(_ value: Double, target: Double, band: Double) -> Bool {
        if target == 0 {
            // Remaining zero: only accept near-zero proposed grams.
            return abs(value) <= 1e-6
        }
        let lower = target * (1 - band)
        let upper = target * (1 + band)
        return value >= lower && value <= upper
    }
}
