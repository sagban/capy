import Foundation

/// Response from callable `lookup_barcode` (Open Food Facts exact GTIN).
struct BarcodeLookupResponseDTO: Codable, Equatable, Sendable {
    var found: Bool
    var foodId: String?
    var displayName: String?
    var brand: String?
    var per100g: MacroTotals?
    var servingGrams: Double?
    var servingLabel: String?
    var source: String?

    /// Usable hit with name + per-100g macros.
    var hit: BarcodeLookupHit? {
        guard found,
              let foodId,
              let displayName,
              !displayName.isEmpty,
              let per100g
        else { return nil }
        return BarcodeLookupHit(
            foodId: foodId,
            displayName: displayName,
            brand: brand?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty,
            per100g: per100g,
            servingGrams: servingGrams.flatMap { $0 > 0 ? $0 : nil },
            servingLabel: servingLabel?.trimmingCharacters(in: .whitespacesAndNewlines).nilIfEmpty,
            source: source ?? "open_food_facts"
        )
    }
}

struct BarcodeLookupHit: Equatable, Sendable {
    var foodId: String
    var displayName: String
    var brand: String?
    var per100g: MacroTotals
    var servingGrams: Double?
    var servingLabel: String?
    var source: String
}

private extension String {
    var nilIfEmpty: String? {
        isEmpty ? nil : self
    }
}
