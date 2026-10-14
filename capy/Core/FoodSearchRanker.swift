import Foundation

/// Ranks catalog search hits so staples beat babyfood / brand noise.
enum FoodSearchRanker {
    private static let noiseTokens = [
        "babyfood", "baby food", "infant", "toddler", "junior",
        "alcoholic", "sake",
        "cereals ready-to-eat", "frozen entree", "fast foods",
        "restaurant", "applebee", "mcdonald", "pizza hut", "wendy",
        "burger king", "subway", "domino", "taco bell",
        "snacks,", "beverages,", "candy", "candies,", "pie,", "cookies",
        "imitation",
    ]

    /// Lower tuple sorts first.
    static func rankKey(
        name: String,
        aliases: [String],
        family: String,
        foodId: String,
        query: String
    ) -> (Int, Int, Int, Int, Int, String) {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let n = name.lowercased()
        let aliasList = aliases.map { $0.lowercased() }
        let match = matchQuality(name: n, aliases: aliasList, family: family.lowercased(), query: q)
        let demote = noisePenalty(name: n)
        let form = formPenalty(name: n, query: q)
        let source = foodId.hasPrefix("seed_") || foodId.hasPrefix("overlay") ? 0 : 1
        return (match, demote, form, source, n.count, n)
    }

    /// For queries under 3 chars: prefix / whole-word only (never bare substring).
    static func shortQueryMatches(query: String, name: String, aliases: [String]) -> Bool {
        let q = query.lowercased()
        let n = name.lowercased()
        let plural = q + "s"
        if n == q || n == plural { return true }
        if n.hasPrefix(q + ",") || n.hasPrefix(q + " ") || n.hasPrefix(plural + ",") { return true }
        if aliases.contains(where: {
            let a = $0.lowercased()
            return a == q || a.hasPrefix(q + " ") || a.hasPrefix(q + ",")
        }) {
            return true
        }
        return wholeWord(q, in: n)
    }

    static func ranked<T>(
        _ items: [T],
        query: String,
        name: (T) -> String,
        aliases: (T) -> [String],
        family: (T) -> String,
        foodId: (T) -> String,
        limit: Int
    ) -> [T] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return Array(items.prefix(limit)) }
        return items
            .map { item in
                (
                    rankKey(
                        name: name(item),
                        aliases: aliases(item),
                        family: family(item),
                        foodId: foodId(item),
                        query: q
                    ),
                    item
                )
            }
            .sorted { $0.0 < $1.0 }
            .prefix(limit)
            .map(\.1)
    }

    private static func matchQuality(name: String, aliases: [String], family: String, query: String) -> Int {
        let plural = query + "s"
        if name == query || name == plural || aliases.contains(query) { return 0 }
        if name.hasPrefix(query + ",") || name.hasPrefix(plural + ",") { return 1 }
        if name.hasPrefix(query + " ") || name.hasPrefix(plural + " ") { return 2 }
        if aliases.contains(where: { $0 == query || $0.hasPrefix(query) }) { return 3 }
        if name.hasPrefix(query) || name.hasPrefix(plural) { return 4 }
        if wholeWord(query, in: name) || wholeWord(plural, in: name) { return 5 }
        if name.contains(query) || aliases.contains(where: { $0.contains(query) }) { return 6 }
        if family.contains(query) { return 7 }
        return 9
    }

    private static func wholeWord(_ query: String, in name: String) -> Bool {
        let pattern = "(^|[\\s,/(-])\(NSRegularExpression.escapedPattern(for: query))($|[\\s,)/])"
        return name.range(of: pattern, options: .regularExpression) != nil
    }

    private static func noisePenalty(name: String) -> Int {
        for token in noiseTokens where name.contains(token) {
            return 10
        }
        return 0
    }

    private static func formPenalty(name: String, query: String) -> Int {
        let wantsRaw = query.contains("raw") || query.contains("uncooked") || query.contains("dry")
        let produceRawOK = ["banana", "apple", "potato", "milk"].contains(query)
        var form = 2
        if name.contains("cooked"), !wantsRaw {
            form = 0
        } else if (wantsRaw || produceRawOK),
                  name.contains(", raw") || name.contains("uncooked") || name.contains("fluid") {
            form = 0
        } else if name.contains(", raw") || name.contains(" uncooked") || name.contains(", dry") {
            form = 3
        }
        let demoteParts = [
            " mix", "flavor", "rice-a-roni", "vermicelli mix",
            "bran", "flour", "cracker", "noodles", "cereal bar",
            "giblet", "gizzard", "heart,", "liver", "neck,", "feet,", "skin only",
            "capons", "stewing", "dehydrated", "powder", "chips", "dried",
            "imitation", "low sodium", "sheep", "buffalo", "buttermilk",
        ]
        if demoteParts.contains(where: { name.contains($0) }) {
            form += 4
        }
        if name.contains("long-grain, regular, enriched, cooked") { return -1 }
        if name.contains("chicken, broilers or fryers, breast"), name.contains("cooked") { return -1 }
        if name.hasPrefix("egg, whole, cooked") { return -1 }
        if name.hasPrefix("bananas, raw") || name.hasPrefix("milk, whole,") { return -1 }
        return form
    }
}
