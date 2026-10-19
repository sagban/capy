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
