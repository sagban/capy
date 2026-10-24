import XCTest
import SwiftData
@testable import capy

@MainActor
final class DiarySyncTests: XCTestCase {
    func testMergeReplacesLocalDiaryWithServerMeals() throws {
        let context = try makeContext()
        let staleId = UUID()
        let stale = MealEntry(dayKey: "2026-10-23", mealSlot: "Breakfast", confirmed: true)
        stale.uuid = staleId
        context.insert(stale)

        let serverId = "22222222-2222-2222-2222-222222222222"
        DiarySyncBuilder.mergeRemote(
            [
                DiaryMealSyncDTO(
                    entryId: serverId,
                    dayKey: "2026-10-23",
                    mealSlot: "Lunch",
                    confirmed: true,
                    deleted: false,
                    items: [
                        DiaryMealItemSyncDTO(
                            name: "Egg",
                            grams: 50,
                            foodId: "seed_egg",
                            source: "seed",
                            per100g: MacroTotals(calories: 155, proteinG: 13, carbsG: 1.1, fatG: 11),
                            ingredientFamily: "egg"
                        )
                    ],
                    createdAt: "2026-10-23T15:00:00Z",
                    updatedAt: nil
                )
            ],
            preserving: .empty,
            into: context
        )

        let entries = try context.fetch(FetchDescriptor<MealEntry>())
        XCTAssertEqual(entries.count, 1)
        XCTAssertEqual(entries[0].uuid.uuidString.lowercased(), serverId)
        XCTAssertEqual(entries[0].mealSlot, "Lunch")
        XCTAssertEqual(entries[0].items.count, 1)
        XCTAssertEqual(entries[0].items[0].grams, 50)
        XCTAssertEqual(entries[0].items[0].calories, 77.5, accuracy: 0.01)
    }

    func testMergeKeepsQueuedLocalLog() throws {
        let context = try makeContext()
        let pendingId = UUID()
        let pending = MealEntry(dayKey: "2026-10-23", mealSlot: "Dinner", confirmed: true)
        pending.uuid = pendingId
        let item = MealEntryItem(name: "Rice", grams: 100, calories: 130, proteinG: 3, carbsG: 28, fatG: 0)
        item.entry = pending
        pending.items = [item]
        context.insert(pending)

        DiarySyncBuilder.mergeRemote(
            [],
            preserving: PendingMealGuards(loggedEntryIds: [pendingId.uuidString.lowercased()], deletedEntryIds: []),
            into: context
        )

        let entries = try context.fetch(FetchDescriptor<MealEntry>())
        XCTAssertEqual(entries.count, 1)
        XCTAssertEqual(entries[0].uuid, pendingId)
    }

    func testMergeDropsServerRowWhenDeleteIsQueued() throws {
        let context = try makeContext()
        let entryId = "33333333-3333-3333-3333-333333333333"
        DiarySyncBuilder.mergeRemote(
            [
                DiaryMealSyncDTO(
                    entryId: entryId,
                    dayKey: "2026-10-23",
                    mealSlot: "Lunch",
                    confirmed: true,
                    deleted: false,
                    items: [
                        DiaryMealItemSyncDTO(
                            name: "Egg",
                            grams: 50,
                            per100g: MacroTotals(calories: 155, proteinG: 13, carbsG: 1.1, fatG: 11)
                        )
                    ],
                    createdAt: nil,
                    updatedAt: nil
                )
            ],
            preserving: PendingMealGuards(loggedEntryIds: [], deletedEntryIds: [entryId]),
            into: context
        )

        let entries = try context.fetch(FetchDescriptor<MealEntry>())
        XCTAssertTrue(entries.isEmpty)
    }

    private func makeContext() throws -> ModelContext {
        let container = try ModelContainer(
            for: Schema([MealEntry.self, MealEntryItem.self]),
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        return ModelContext(container)
    }
}
