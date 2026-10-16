import Foundation

enum PendingSyncKind: String, Codable {
    case logMeal
    case deleteMeal
    case patchProfile
}

struct PendingSyncOperation: Codable, Identifiable, Equatable {
    var id: UUID
    var kind: PendingSyncKind
    var enqueuedAt: Date
    var logMeal: LogMealPayload?
    var deleteMeal: DeleteMealPayload?
    var patchProfile: PatchProfilePayload?

    static func logMeal(_ payload: LogMealPayload) -> PendingSyncOperation {
        PendingSyncOperation(
            id: UUID(),
            kind: .logMeal,
            enqueuedAt: .now,
            logMeal: payload,
            deleteMeal: nil,
            patchProfile: nil
        )
    }

    static func deleteMeal(_ payload: DeleteMealPayload) -> PendingSyncOperation {
        PendingSyncOperation(
            id: UUID(),
            kind: .deleteMeal,
            enqueuedAt: .now,
            logMeal: nil,
            deleteMeal: payload,
            patchProfile: nil
        )
    }

    static func patchProfile(_ payload: PatchProfilePayload) -> PendingSyncOperation {
        PendingSyncOperation(
            id: UUID(),
            kind: .patchProfile,
            enqueuedAt: .now,
            logMeal: nil,
            deleteMeal: nil,
            patchProfile: payload
        )
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
        pending.append(operation)
        save(pending)
    }

    func dequeueAll() -> [PendingSyncOperation] {
        load()
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
