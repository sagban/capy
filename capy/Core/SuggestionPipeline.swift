import Foundation

/// Candidate meal item with catalog-backed macros (never LLM totals).
struct PipelineCandidate: Equatable, Sendable, Identifiable {
    var id: String { foodId }
    var foodId: String
    var displayName: String
    var ingredientFamily: String
    var grams: Double
    var per100g: MacroTotals

    var macros: MacroTotals {
        MacroMath.scale(per100g: per100g, grams: grams)
    }
}

enum SuggestionPipelineOutcome: Equatable, Sendable {
    case accepted(PipelineCandidate)
    case abstain(reasons: [VerifyRejectionReason])
}

/// On-device suggestion path: variety → MacroMath → verifier → abstain.
enum SuggestionPipeline {
    /// Rank/filter candidates, then verify scaled macros against remaining (±10%, max 3 attempts).
    static func run(
        candidates: [PipelineCandidate],
        remaining: MacroTotals,
        todayFamilies: Set<String>,
        dayKeysLast7: [String],
        foodIdsByDay: [String: Set<String>],
        excludingFoodIds: Set<String> = [],
        budget: SuggestionBudget? = nil
    ) -> SuggestionPipelineOutcome {
        let eligible = candidates.filter { !excludingFoodIds.contains($0.foodId) }
        let ranked = VarietyFilter.filterAndRank(
            candidates: eligible,
            familyOf: \.ingredientFamily,
            foodIdOf: \.foodId,
            todayFamilies: todayFamilies,
            dayKeysLast7: dayKeysLast7,
            foodIdsByDay: foodIdsByDay
        )
        guard !ranked.isEmpty else {
            return .abstain(reasons: [.caloriesExceedRemaining])
        }

        var reasons: [VerifyRejectionReason] = []
        for candidate in ranked.prefix(6) {
            switch SuggestionVerifier.verifyFit(
                proposed: candidate.macros,
                remaining: remaining,
                budget: budget
            ) {
            case .accepted:
                return .accepted(candidate)
            case .rejected(let reason, _):
                reasons.append(reason)
            case .abstain(let already):
                reasons.append(contentsOf: already)
            }
        }
        return .abstain(reasons: reasons.isEmpty ? [.caloriesExceedRemaining] : reasons)
    }

    static func abstainMessage(reasons: [VerifyRejectionReason]) -> String {
        if reasons.contains(.caloriesExceedRemaining) {
            return "nothing that fits remaining calories cleanly"
        }
        if reasons.contains(where: {
            $0 == .proteinOutOfBand || $0 == .carbsOutOfBand || $0 == .fatOutOfBand
        }) {
            return "nothing that fits that budget — try a bigger one"
        }
        return "nothing that fits cleanly"
    }
}
