import Foundation

struct PendingMealGuards: Equatable, Sendable {
    var loggedEntryIds: Set<String>
    var deletedEntryIds: Set<String>

    static let empty = PendingMealGuards(loggedEntryIds: [], deletedEntryIds: [])

    func protects(_ entryId: String) -> Bool {
        let key = entryId.lowercased()
        return loggedEntryIds.contains(key) || deletedEntryIds.contains(key)
    }
}

/// Durable outbound queue (UserDefaults) for offline profile and meal writes.
actor ServerSyncQueue {
    static let shared = ServerSyncQueue()

    private let defaultsKey = "capy.serverSync.pending"
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    func enqueue(_ operation: PendingSyncOperation) {
        var pending = load()
        if operation.kind == .logMeal, let mutationId = operation.logMeal?.clientMutationId {
            pending.removeAll { $0.logMeal?.clientMutationId == mutationId }
        }
        if operation.kind == .deleteMeal, let mutationId = operation.deleteMeal?.clientMutationId {
            pending.removeAll { $0.deleteMeal?.clientMutationId == mutationId }
        }
        if operation.kind == .patchProfile {
            pending.removeAll { $0.kind == .patchProfile }
        }
        if operation.kind == .upsertLibraryItem, let itemId = operation.upsertLibraryItem?.item.id {
            pending.removeAll {
                $0.upsertLibraryItem?.item.id == itemId || $0.deleteLibraryItem?.id == itemId
            }
        }
        if operation.kind == .deleteLibraryItem, let itemId = operation.deleteLibraryItem?.id {
            pending.removeAll {
                $0.upsertLibraryItem?.item.id == itemId || $0.deleteLibraryItem?.id == itemId
            }
        }
        pending.append(operation)
        save(pending)
    }

    func dequeueAll() -> [PendingSyncOperation] {
        load()
    }

    /// Meal ids with a log or delete still waiting to reach the server.
    func pendingMealGuards() -> PendingMealGuards {
        var logged = Set<String>()
        var deleted = Set<String>()
        for operation in load() {
            if let entryId = operation.logMeal?.entryId.trimmingCharacters(in: .whitespacesAndNewlines),
               !entryId.isEmpty {
                logged.insert(entryId.lowercased())
            }
            if let entryId = operation.deleteMeal?.entryId.trimmingCharacters(in: .whitespacesAndNewlines),
               !entryId.isEmpty {
                deleted.insert(entryId.lowercased())
            }
        }
        return PendingMealGuards(loggedEntryIds: logged, deletedEntryIds: deleted)
    }

    func remove(ids: Set<UUID>) {
        guard !ids.isEmpty else { return }
        let pending = load().filter { !ids.contains($0.id) }
        save(pending)
    }

    private func load() -> [PendingSyncOperation] {
        guard let data = UserDefaults.standard.data(forKey: defaultsKey) else { return [] }
        return (try? decoder.decode([PendingSyncOperation].self, from: data)) ?? []
    }

    private func save(_ operations: [PendingSyncOperation]) {
        guard let data = try? encoder.encode(operations) else { return }
        UserDefaults.standard.set(data, forKey: defaultsKey)
    }
}
