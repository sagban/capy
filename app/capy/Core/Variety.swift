import Foundation

/// Ingredient-family variety: same-day hard block + 7-day soft repetition decay.
enum VarietyFilter {
    /// Families already logged today are hard-blocked from suggestions.
    static func hardBlockedFamilies(todayFamilies: Set<String>) -> Set<String> {
        Set(todayFamilies.map { $0.lowercased() })
    }

    /// Returns candidates whose `ingredientFamily` is not in today's hard block.
    static func applyHardFilter<T>(
        candidates: [T],
        familyOf: (T) -> String,
        todayFamilies: Set<String>
    ) -> [T] {
        let blocked = hardBlockedFamilies(todayFamilies: todayFamilies)
        return candidates.filter { !blocked.contains(familyOf($0).lowercased()) }
    }

    /// Soft decay: foods appearing on 3+ of the last 7 days rank down (not out).
    /// Score is daysSeen in the window; higher = more repeated = worse for ranking.
    static func repetitionDays(
        foodId: String,
        dayKeysLast7: [String],
        foodIdsByDay: [String: Set<String>]
    ) -> Int {
        dayKeysLast7.reduce(0) { count, day in
            count + ((foodIdsByDay[day]?.contains(foodId) == true) ? 1 : 0)
        }
    }

    /// Stable sort: lower repetition first, then original index for determinism.
    static func rankByDecay<T>(
        candidates: [T],
        foodIdOf: (T) -> String,
        dayKeysLast7: [String],
        foodIdsByDay: [String: Set<String>],
        decayThreshold: Int = 3
    ) -> [T] {
        candidates.enumerated()
            .map { index, item in
                let days = repetitionDays(
                    foodId: foodIdOf(item),
                    dayKeysLast7: dayKeysLast7,
                    foodIdsByDay: foodIdsByDay
                )
                let penalty = days >= decayThreshold ? days : 0
                return (penalty, index, item)
            }
            .sorted { lhs, rhs in
                if lhs.0 != rhs.0 { return lhs.0 < rhs.0 }
                return lhs.1 < rhs.1
            }
            .map(\.2)
    }

    /// Hard filter then soft decay ranking.
    static func filterAndRank<T>(
        candidates: [T],
        familyOf: (T) -> String,
        foodIdOf: (T) -> String,
        todayFamilies: Set<String>,
        dayKeysLast7: [String],
        foodIdsByDay: [String: Set<String>]
    ) -> [T] {
        let filtered = applyHardFilter(
            candidates: candidates,
            familyOf: familyOf,
            todayFamilies: todayFamilies
        )
        return rankByDecay(
            candidates: filtered,
            foodIdOf: foodIdOf,
            dayKeysLast7: dayKeysLast7,
            foodIdsByDay: foodIdsByDay
        )
    }
}
