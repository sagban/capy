import Foundation

/// Edible default portion when catalog has no USDA/overlay `servingGrams`.
enum PortionDefaults {
    static func servingGrams(
        family: String,
        name: String,
        kcalPer100g: Double
    ) -> Double {
        let fam = family.lowercased()
        let n = name.lowercased()
        if fam == "fat" || n.contains("oil") || (kcalPer100g >= 700 && fam != "nut") {
            return 14 // 1 tbsp
        }
        if fam == "egg" {
            return n.contains("white") ? 33 : 50
        }
        if fam == "nut" {
            return 28
        }
        if fam == "spice" {
            return 5
        }
        if fam == "supplement" || n.contains("protein powder") || n.contains("whey") {
            return 30
        }
        return 100
    }

    static func scaledMacros(per100g: MacroTotals, grams: Double) -> MacroTotals {
        MacroMath.scale(per100g: per100g, grams: grams)
    }
}
