import Foundation

/// Client-side recent corrections for ContextBuilder memory snapshot.
enum RecentCorrectionStore {
    private static let storageKey = "capy.recentCorrections"

    private struct Stored: Codable {
        var dayKey: String
        var text: String
        var at: String
    }

    static func append(text: String, dayKey: String, at: Date = .now) {
        var items = load().filter { $0.dayKey == dayKey }
        let formatter = ISO8601DateFormatter()
        items.insert(
            Stored(dayKey: dayKey, text: text, at: formatter.string(from: at)),
            at: 0
        )
        if items.count > 8 {
            items = Array(items.prefix(8))
        }
        if let data = try? JSONEncoder().encode(items) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }

    static func recent(dayKey: String, limit: Int = 5) -> [RecentCorrectionDTO] {
        Array(
            load()
                .filter { $0.dayKey == dayKey }
                .prefix(limit)
                .map { RecentCorrectionDTO(text: $0.text, at: $0.at) }
        )
    }

    private static func load() -> [Stored] {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let items = try? JSONDecoder().decode([Stored].self, from: data)
        else { return [] }
        return items
    }
}
