import XCTest
import SwiftData
@testable import capy

final class MealCommitTests: XCTestCase {
    func testLogNewEntriesUpsertsAILibraryAndSyncsShape() throws {
        let container = try ModelContainer(
            for: Schema([MealEntry.self, MealEntryItem.self, capy.LibraryItem.self]),
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let context = ModelContext(container)
        let line = MealCommitLine(
            name: "Quiche",
            foodId: "web_q",
            grams: 150,
            calories: 420,
            proteinG: 18,
            carbsG: 28,
            fatG: 26,
            source: "web",
            per100g: MacroTotals(calories: 280, proteinG: 12, carbsG: 18.666, fatG: 17.333),
            citationUrl: "https://example.com",
            portionLabel: "1 slice"
        )
        let result = MealCommit.logNewEntries(
            lines: [line],
            dayKey: "2026-10-19",
            mealSlot: "Lunch",
            upsertAILibrary: true,
            in: context
        )
        XCTAssertEqual(result.names, ["Quiche"])
        XCTAssertEqual(result.added.calories, 420, accuracy: 1)
        let entries = try context.fetch(FetchDescriptor<MealEntry>())
        XCTAssertEqual(entries.count, 1)
        XCTAssertEqual(entries.first?.items.count, 1)
        let library = try context.fetch(FetchDescriptor<capy.LibraryItem>())
        XCTAssertEqual(library.count, 1)
        XCTAssertEqual(library.first?.origin, .aiGenerated)
    }

    func testLoggedReplyQuietOmitsCalorieTotal() {
        let reply = MealCommit.loggedReply(
            names: ["Egg", "Toast"],
            added: MacroTotals(calories: 300, proteinG: 20, carbsG: 30, fatG: 10),
            eatenBefore: .zero,
            target: MacroTotals(calories: 2000, proteinG: 140, carbsG: 200, fatG: 65),
            assistance: .quiet
        )
        XCTAssertTrue(reply.contains("Egg and Toast"))
        XCTAssertFalse(reply.contains("300 cal"))
        XCTAssertTrue(reply.contains("left"))
    }
}
