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

    func testAcceptedWebItemUpsertsAIGeneratedLibraryFood() throws {
        let container = try ModelContainer(
            for: Schema([capy.LibraryItem.self]),
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let context = ModelContext(container)
        let per100g = MacroTotals(calories: 280, proteinG: 12, carbsG: 20, fatG: 16)
        let saved = capy.LibraryItem.upsertFromAcceptedAgentLine(
            name: "Quiche",
            foodId: "web_abc",
            grams: 150,
            per100g: per100g,
            source: "web",
            citationUrl: "https://toast.app",
            portionLabel: "1 slice (150 g)",
            in: context
        )
        XCTAssertNotNil(saved)
        XCTAssertEqual(saved?.origin, .aiGenerated)
        XCTAssertEqual(saved?.kind, .food)
        XCTAssertEqual(saved?.sourceFoodId, "web_abc")
        XCTAssertEqual(saved?.servingGrams ?? 0, 150, accuracy: 0.01)
        XCTAssertEqual(saved?.calories ?? 0, 420, accuracy: 0.5)
        XCTAssertEqual(saved?.agentServingGrams ?? 0, 150, accuracy: 0.01)

        let again = capy.LibraryItem.upsertFromAcceptedAgentLine(
            name: "Quiche Lorraine",
            foodId: "web_abc",
            grams: 160,
            per100g: per100g,
            source: "web",
            citationUrl: nil,
            portionLabel: "1 slice",
            in: context
        )
        XCTAssertEqual(again?.uuidString, saved?.uuidString)
        XCTAssertEqual(again?.name, "Quiche Lorraine")
        let all = try context.fetch(FetchDescriptor<capy.LibraryItem>())
        XCTAssertEqual(all.count, 1)
    }

    func testCatalogConfirmDoesNotEnterAILibrary() throws {
        let container = try ModelContainer(
            for: Schema([capy.LibraryItem.self]),
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let context = ModelContext(container)
        let saved = capy.LibraryItem.upsertFromAcceptedAgentLine(
            name: "Egg",
            foodId: "seed_egg",
            grams: 100,
            per100g: MacroTotals(calories: 155, proteinG: 13, carbsG: 1, fatG: 11),
            source: "catalog",
            citationUrl: nil,
            portionLabel: "2 large",
            in: context
        )
        XCTAssertNil(saved)
        let all = try context.fetch(FetchDescriptor<capy.LibraryItem>())
        XCTAssertTrue(all.isEmpty)
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
