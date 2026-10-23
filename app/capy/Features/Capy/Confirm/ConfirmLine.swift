import Foundation

struct ConfirmLine: Identifiable, Equatable {
    var id: String
    var name: String
    var foodId: String
    var grams: Double
    var per100g: MacroTotals
    var source: String
    var citationUrl: String?
    var portionLabel: String?
    var family: String
    var entryId: String?
    var itemIndex: Int?
    var priorGrams: Double?

    var macros: MacroTotals {
        MacroMath.scale(per100g: per100g, grams: grams)
    }

    var commitLine: MealCommitLine {
        MealCommitLine(confirmLine: self)
    }
}

enum SourceBadge {
    static func title(for source: String) -> String? {
        switch source {
        case "estimate": "estimate"
        case "web": "web"
        default: nil
        }
    }
}

enum ConfirmMath {
    static func totals(_ lines: [ConfirmLine]) -> MacroTotals {
        lines.reduce(.zero) { partial, line in
            partial + line.macros
        }
    }
}

struct PendingDeleteContext: Equatable {
    var entryId: String
    var dayKey: String
    var label: String
}
