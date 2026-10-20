import Foundation
import FirebaseAuth
import Network
import SwiftData

@MainActor
final class UserSyncService {
    static let shared = UserSyncService()

    private var profileSyncTask: Task<Void, Never>?
    private let monitor = NWPathMonitor()
    private var isNetworkReachable = true

    private init() {}

    func start() async {
        monitor.pathUpdateHandler = { [weak self] path in
            let reachable = path.status == .satisfied
            Task { @MainActor in
                guard let self else { return }
                let wasOffline = !self.isNetworkReachable
                self.isNetworkReachable = reachable
                if wasOffline && reachable {
                    await self.flushPending()
                }
            }
        }
        monitor.start(queue: DispatchQueue(label: "capy.network.monitor"))
        await flushPending()
    }

    func scheduleProfileSync(in modelContext: ModelContext) {
        profileSyncTask?.cancel()
        profileSyncTask = Task { @MainActor in
            try? await Task.sleep(for: .seconds(1.5))
            guard !Task.isCancelled else { return }
            let payload = ProfileSyncBuilder.patchPayload(modelContext: modelContext)
            await ServerSyncQueue.shared.enqueue(.patchProfile(payload))
            await flushPending()
        }
    }

    func enqueueLogMeal(_ entry: MealEntry, clientMutationId: String = UUID().uuidString) {
        guard let payload = MealLogSyncBuilder.payload(for: entry, clientMutationId: clientMutationId) else {
            return
        }
        Task {
            await ServerSyncQueue.shared.enqueue(.logMeal(payload))
            await flushPending()
        }
    }

    func enqueueDeleteMeal(
        entryId: String,
        dayKey: String,
        clientMutationId: String = UUID().uuidString
    ) {
        let trimmedEntry = entryId.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedDay = dayKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedEntry.isEmpty, !trimmedDay.isEmpty else { return }
        let payload = DeleteMealPayload(
            clientMutationId: clientMutationId,
            dayKey: trimmedDay,
            entryId: trimmedEntry
        )
        Task {
            await ServerSyncQueue.shared.enqueue(.deleteMeal(payload))
            await flushPending()
        }
    }

    func enqueueUpsertLibrary(_ item: LibraryItem, clientMutationId: String = UUID().uuidString) {
        let payload = LibrarySyncBuilder.upsertPayload(for: item, clientMutationId: clientMutationId)
        Task {
            await ServerSyncQueue.shared.enqueue(.upsertLibraryItem(payload))
            await flushPending()
        }
    }

    func enqueueDeleteLibrary(id: String, clientMutationId: String = UUID().uuidString) {
        let trimmed = id.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let payload = LibrarySyncBuilder.deletePayload(id: trimmed, clientMutationId: clientMutationId)
        Task {
            await ServerSyncQueue.shared.enqueue(.deleteLibraryItem(payload))
            await flushPending()
        }
    }

    /// Pull Firestore library into SwiftData, then push any local-only rows.
    func pullLibrary(into modelContext: ModelContext) async {
        guard isNetworkReachable else { return }
        guard Auth.auth().currentUser != nil else { return }
        do {
            let raw = try await AgentClient.shared.callCallable(
                "list_library",
                payload: ["includeDeleted": true]
            )
            let data = try JSONSerialization.data(withJSONObject: raw)
            let response = try JSONDecoder().decode(ListLibraryResponseDTO.self, from: data)
            LibrarySyncBuilder.mergeRemote(response.items, into: modelContext)
            await flushPending()
        } catch {
            #if DEBUG
            print("[UserSyncService] list_library failed: \(error)")
            #endif
        }
    }

    func flushPending() async {
        guard isNetworkReachable else { return }
        guard Auth.auth().currentUser != nil else { return }

        let pending = await ServerSyncQueue.shared.dequeueAll()
        guard !pending.isEmpty else { return }

        var completed: Set<UUID> = []
        for operation in pending {
            do {
                switch operation.kind {
                case .logMeal:
                    guard let payload = operation.logMeal else { continue }
                    let dict = try Self.encode(payload)
                    _ = try await AgentClient.shared.callCallable("log_meal", payload: dict)
                case .deleteMeal:
                    guard let payload = operation.deleteMeal else { continue }
                    let dict = try Self.encode(payload)
                    _ = try await AgentClient.shared.callCallable("delete_meal", payload: dict)
                case .patchProfile:
                    guard let payload = operation.patchProfile else { continue }
                    let dict = try Self.encode(payload)
                    _ = try await AgentClient.shared.callCallable("patch_profile", payload: dict)
                case .upsertLibraryItem:
                    guard let payload = operation.upsertLibraryItem else { continue }
                    let dict = try Self.encode(payload)
                    _ = try await AgentClient.shared.callCallable("upsert_library_item", payload: dict)
                case .deleteLibraryItem:
                    guard let payload = operation.deleteLibraryItem else { continue }
                    let dict = try Self.encode(payload)
                    _ = try await AgentClient.shared.callCallable("delete_library_item", payload: dict)
                }
                completed.insert(operation.id)
            } catch {
                #if DEBUG
                print("[UserSyncService] flush failed \(operation.kind): \(error)")
                #endif
            }
        }
        if !completed.isEmpty {
            await ServerSyncQueue.shared.remove(ids: completed)
        }
    }

    private static func encode<T: Encodable>(_ value: T) throws -> [String: Any] {
        let data = try JSONEncoder().encode(value)
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw AgentClientError.unavailable
        }
        return AgentClient.stripNulls(object)
    }
}
