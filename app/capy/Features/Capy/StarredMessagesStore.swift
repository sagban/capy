import Foundation

struct StarredMessage: Codable, Identifiable, Equatable {
    var id: String
    var role: String
    var text: String
}

/// Stars live on this phone for the signed-in account. Resetting the chat clears them with that account's thread.
@MainActor
@Observable
final class StarredMessagesStore {
    static let shared = StarredMessagesStore()

    private static let legacyKey = "capy.starredMessages.v1"
    private var storageKey: String?
    private(set) var items: [StarredMessage] = []

    private init() {}

    func useAccount(_ uid: String?) {
        guard let uid, !uid.isEmpty else {
            storageKey = nil
            items = []
            return
        }
        let key = "\(Self.legacyKey).\(uid)"
        guard key != storageKey else { return }
        storageKey = key
        UserDefaults.standard.removeObject(forKey: Self.legacyKey)
        items = Self.load(key)
    }

    func isStarred(_ id: String) -> Bool {
        items.contains { $0.id == id }
    }

    func toggle(id: String, role: ChatBubble.Role, text: String) {
        if let index = items.firstIndex(where: { $0.id == id }) {
            items.remove(at: index)
        } else {
            let roleName = role == .user ? "user" : "capy"
            items.insert(StarredMessage(id: id, role: roleName, text: text), at: 0)
        }
        save()
    }

    func clear() {
        items = []
        save()
    }

    private func save() {
        guard let storageKey, let data = try? JSONEncoder().encode(items) else { return }
        UserDefaults.standard.set(data, forKey: storageKey)
    }

    private static func load(_ key: String) -> [StarredMessage] {
        guard let data = UserDefaults.standard.data(forKey: key),
              let decoded = try? JSONDecoder().decode([StarredMessage].self, from: data) else {
            return []
        }
        return decoded
    }
}
