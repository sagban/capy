import Foundation
import SwiftData

enum LibrarySyncBuilder {
    private static let isoFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let isoFormatterPlain: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    static func syncDTO(for item: LibraryItem) -> LibraryItemSyncDTO {
        LibraryItemSyncDTO(
            id: item.uuidString,
            name: item.name,
            kind: item.kind.rawValue,
            origin: item.origin.rawValue,
            detail: item.detail,
            calories: item.calories,
            proteinG: item.proteinG,
            carbsG: item.carbsG,
            fatG: item.fatG,
            servingGrams: max(item.servingGrams, 1),
            sourceFoodId: item.sourceFoodId,
            ingredients: item.ingredients,
            createdAt: isoString(item.createdAt),
            updatedAt: isoString(item.updatedAt),
            deleted: false
        )
    }

    static func upsertPayload(
        for item: LibraryItem,
        clientMutationId: String = UUID().uuidString
    ) -> UpsertLibraryItemPayload {
        UpsertLibraryItemPayload(clientMutationId: clientMutationId, item: syncDTO(for: item))
    }

    static func deletePayload(
        id: String,
        clientMutationId: String = UUID().uuidString
    ) -> DeleteLibraryItemPayload {
        DeleteLibraryItemPayload(clientMutationId: clientMutationId, id: id)
    }

    /// Merge remote library into local SwiftData, then enqueue upserts for local-only rows.
    @MainActor
    static func mergeRemote(
        _ remote: [LibraryItemSyncDTO],
        into context: ModelContext
    ) {
        var descriptor = FetchDescriptor<LibraryItem>()
        let local = (try? context.fetch(descriptor)) ?? []
        var byId = Dictionary(uniqueKeysWithValues: local.map { ($0.uuidString, $0) })

        var remoteIds = Set<String>()
        for row in remote {
            let id = row.id.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !id.isEmpty else { continue }
            remoteIds.insert(id)

            if row.deleted == true {
                if let existing = byId[id] {
                    context.delete(existing)
                    byId.removeValue(forKey: id)
                }
                continue
            }

            let name = row.name.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !name.isEmpty else { continue }

            if let existing = byId[id] {
                apply(row, to: existing)
            } else {
                let item = LibraryItem(
                    name: name,
                    kind: LibraryKind(rawValue: row.kind) ?? .food,
                    origin: LibraryOrigin(rawValue: row.origin) ?? .user,
                    detail: row.detail,
                    calories: row.calories,
                    proteinG: row.proteinG,
                    carbsG: row.carbsG,
                    fatG: row.fatG,
                    ingredients: row.ingredients,
                    sourceFoodId: row.sourceFoodId,
                    servingGrams: max(row.servingGrams, 1),
                    createdAt: parseDate(row.createdAt) ?? .now
                )
                item.uuidString = id
                item.updatedAt = parseDate(row.updatedAt) ?? item.createdAt
                context.insert(item)
                byId[id] = item
            }
        }

        try? context.save()

        // Bootstrap: push local items the server has never seen.
        for item in byId.values where !remoteIds.contains(item.uuidString) {
            UserSyncService.shared.enqueueUpsertLibrary(item)
        }
    }

    private static func apply(_ row: LibraryItemSyncDTO, to item: LibraryItem) {
        item.name = row.name
        item.kind = LibraryKind(rawValue: row.kind) ?? item.kind
        item.origin = LibraryOrigin(rawValue: row.origin) ?? item.origin
        item.detail = row.detail
        item.calories = row.calories
        item.proteinG = row.proteinG
        item.carbsG = row.carbsG
        item.fatG = row.fatG
        item.servingGrams = max(row.servingGrams, 1)
        item.sourceFoodId = row.sourceFoodId
        item.ingredients = row.ingredients
        if let created = parseDate(row.createdAt) {
            item.createdAt = created
        }
        item.updatedAt = parseDate(row.updatedAt) ?? .now
    }

    private static func isoString(_ date: Date) -> String {
        isoFormatter.string(from: date)
    }

    private static func parseDate(_ raw: String?) -> Date? {
        guard let raw, !raw.isEmpty else { return nil }
        return isoFormatter.date(from: raw) ?? isoFormatterPlain.date(from: raw)
    }
}
