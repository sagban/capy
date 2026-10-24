import Foundation
import SwiftData

enum DiarySyncBuilder {
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

    /// Replace the local diary with the server diary.
    /// Rows still queued for upload or delete stay until that flush finishes.
    @MainActor
    static func mergeRemote(
        _ remote: [DiaryMealSyncDTO],
        preserving pending: PendingMealGuards,
        into context: ModelContext
    ) {
        let local = (try? context.fetch(FetchDescriptor<MealEntry>())) ?? []
        var byId = Dictionary(uniqueKeysWithValues: local.map { ($0.uuid.uuidString.lowercased(), $0) })
        var remoteIds = Set<String>()

        for row in remote {
            let id = row.entryId.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            guard !id.isEmpty, UUID(uuidString: id) != nil else { continue }
            remoteIds.insert(id)
            if pending.protects(id) { continue }

            if row.deleted == true || row.confirmed == false {
                if let existing = byId[id] {
                    delete(existing, in: context)
                    byId.removeValue(forKey: id)
                }
                continue
            }

            if let existing = byId[id] {
                apply(row, to: existing, in: context)
                if existing.items.isEmpty {
                    delete(existing, in: context)
                    byId.removeValue(forKey: id)
                }
            } else if let created = makeEntry(row, id: id, in: context) {
                byId[id] = created
            }
        }

        for (id, entry) in byId where !remoteIds.contains(id) && !pending.loggedEntryIds.contains(id) {
            delete(entry, in: context)
        }

        try? context.save()
    }

    @MainActor
    private static func makeEntry(
        _ row: DiaryMealSyncDTO,
        id: String,
        in context: ModelContext
    ) -> MealEntry? {
        guard let uuid = UUID(uuidString: id) else { return nil }
        let entry = MealEntry(
            timestamp: parseDate(row.createdAt) ?? parseDate(row.updatedAt) ?? .now,
            dayKey: row.dayKey,
            mealSlot: slot(row.mealSlot),
            confirmed: true,
            items: []
        )
        entry.uuid = uuid
        context.insert(entry)
        apply(row, to: entry, in: context)
        guard !entry.items.isEmpty else {
            context.delete(entry)
            return nil
        }
        return entry
    }

    @MainActor
    private static func apply(_ row: DiaryMealSyncDTO, to entry: MealEntry, in context: ModelContext) {
        entry.dayKey = row.dayKey
        entry.mealSlot = slot(row.mealSlot)
        entry.confirmed = true
        if let created = parseDate(row.createdAt) {
            entry.timestamp = created
        }
        replaceItems(row.items, on: entry, in: context)
        let names = entry.items.map(\.name).filter { !$0.isEmpty }
        if !names.isEmpty {
            entry.originalUserText = names.joined(separator: ", ")
        }
    }

    @MainActor
    private static func replaceItems(
        _ items: [DiaryMealItemSyncDTO],
        on entry: MealEntry,
        in context: ModelContext
    ) {
        for item in entry.items {
            context.delete(item)
        }
        entry.items.removeAll()
        for raw in items {
            let name = raw.name.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !name.isEmpty, raw.grams > 0 else { continue }
            let macros = scaled(raw.per100g, grams: raw.grams)
            let item = MealEntryItem(
                name: name,
                grams: raw.grams,
                calories: macros.calories,
                proteinG: macros.proteinG,
                carbsG: macros.carbsG,
                fatG: macros.fatG,
                foodId: raw.foodId ?? "",
                ingredientFamily: raw.ingredientFamily ?? "",
                source: raw.source ?? ""
            )
            item.entry = entry
            entry.items.append(item)
        }
    }

    private static func scaled(_ per: MacroTotals?, grams: Double) -> MacroTotals {
        guard let per, grams > 0 else { return .zero }
        let factor = grams / 100
        return MacroTotals(
            calories: per.calories * factor,
            proteinG: per.proteinG * factor,
            carbsG: per.carbsG * factor,
            fatG: per.fatG * factor
        )
    }

    private static func slot(_ raw: String?) -> String? {
        let trimmed = raw?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return trimmed.isEmpty ? nil : trimmed
    }

    @MainActor
    private static func delete(_ entry: MealEntry, in context: ModelContext) {
        for item in entry.items {
            context.delete(item)
        }
        context.delete(entry)
    }

    private static func parseDate(_ raw: String?) -> Date? {
        guard let raw, !raw.isEmpty else { return nil }
        return isoFormatter.date(from: raw) ?? isoFormatterPlain.date(from: raw)
    }
}
