import XCTest
import SwiftData
@testable import capy

final class AgentContractTests: XCTestCase {
    func testConfirmTotalsScaleEachLine() {
        let lines = [
            ConfirmLine(
                id: "a",
                name: "Egg",
                foodId: "seed_egg",
                grams: 100,
                per100g: MacroTotals(calories: 155, proteinG: 13, carbsG: 1, fatG: 11),
                source: "catalog",
                citationUrl: nil,
                portionLabel: "2 large",
                family: "egg",
                entryId: nil,
                itemIndex: nil,
                priorGrams: nil
            ),
            ConfirmLine(
                id: "b",
                name: "Rice",
                foodId: "seed_rice",
                grams: 50,
                per100g: MacroTotals(calories: 130, proteinG: 2, carbsG: 28, fatG: 0),
                source: "estimate",
                citationUrl: nil,
                portionLabel: nil,
                family: "",
                entryId: nil,
                itemIndex: nil,
                priorGrams: nil
            ),
        ]
        let totals = ConfirmMath.totals(lines)
        XCTAssertEqual(totals.calories, 155 + 65, accuracy: 0.01)
        XCTAssertEqual(SourceBadge.title(for: "estimate"), "estimate")
        XCTAssertEqual(SourceBadge.title(for: "web"), "web")
        XCTAssertNil(SourceBadge.title(for: "catalog"))
    }

    func testDiaryItemsCarryEntryIdAndIndex() throws {
        let container = try ModelContainer(
            for: Schema([MealEntry.self, MealEntryItem.self]),
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let context = ModelContext(container)
        let item = MealEntryItem(
            name: "Egg",
            grams: 100,
            calories: 155,
            proteinG: 13,
            carbsG: 1.1,
            fatG: 11,
            foodId: "seed_egg",
            ingredientFamily: "egg",
            source: "catalog"
        )
        let entry = MealEntry(dayKey: "2026-10-13", mealSlot: "breakfast", items: [item])
        context.insert(entry)
        let payload = MealLogSyncBuilder.payload(for: entry, clientMutationId: "test-mutation")
        XCTAssertNotNil(payload)
        XCTAssertEqual(payload?.entryId, entry.uuid.uuidString)
        XCTAssertEqual(payload?.items.count, 1)
        XCTAssertEqual(payload?.items[0].foodId, "seed_egg")
        XCTAssertEqual(payload?.items[0].source, "catalog")
        XCTAssertEqual(payload?.items[0].per100g?.calories ?? 0, 155, accuracy: 0.01)
    }
}
