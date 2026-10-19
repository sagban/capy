import XCTest
import SwiftData
@testable import capy

final class SeedImporterTests: XCTestCase {
    func testImportAllIdempotent() throws {
        let schema = Schema([Food.self, MealTemplate.self, MealTemplateItem.self])
        let container = try ModelContainer(
            for: schema,
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let context = ModelContext(container)
        let url = Bundle.main.url(forResource: "SeedFoods", withExtension: "json")
            ?? Bundle(for: SeedImporterTests.self).url(forResource: "SeedFoods", withExtension: "json")
        let data: Data
        if let url {
            data = try Data(contentsOf: url)
        } else {
            // Fall back to repo draft path when not bundled into test host.
            let path = URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .appendingPathComponent("capy/Resources/SeedFoods.json")
            data = try Data(contentsOf: path)
        }
        let file = try JSONDecoder().decode(SeedImporter.SeedFile.self, from: data)
        try SeedImporter.importAll(file: file, into: context)
        let firstCount = try context.fetch(FetchDescriptor<Food>()).count
        XCTAssertGreaterThan(firstCount, 10)
        try SeedImporter.importAll(file: file, into: context)
        let secondCount = try context.fetch(FetchDescriptor<Food>()).count
        XCTAssertEqual(firstCount, secondCount)
        XCTAssertGreaterThan(firstCount, 1000)
        let rice = try context.fetch(
            FetchDescriptor<Food>(predicate: #Predicate { $0.id == "usda_168878" })
        ).first
        XCTAssertNotNil(rice)
        XCTAssertEqual(rice?.source, .usda)
        let paneer = try context.fetch(
            FetchDescriptor<Food>(predicate: #Predicate { $0.id == "seed_paneer" })
        ).first
        XCTAssertEqual(paneer?.ingredientFamily, "dairy")
        XCTAssertEqual(paneer!.servingGrams, 50, accuracy: 0.1)

        let eggWhite = try context.fetch(
            FetchDescriptor<Food>(predicate: #Predicate { $0.id == "usda_747997" })
        ).first
        XCTAssertNotNil(eggWhite)
        XCTAssertGreaterThan(eggWhite!.servingGrams, 0)
        XCTAssertLessThan(eggWhite!.servingGrams, 50)

        let olive = try context.fetch(
            FetchDescriptor<Food>(predicate: #Predicate { $0.id == "usda_171413" })
        ).first
        XCTAssertNotNil(olive)
        XCTAssertEqual(olive!.servingGrams, 13.5, accuracy: 0.5)
    }

    func testSearchFoodsEmptyQueryReturnsNothing() throws {
        let schema = Schema([Food.self, MealTemplate.self, MealTemplateItem.self])
        let container = try ModelContainer(
            for: schema,
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        let context = ModelContext(container)
        context.insert(
            Food(
                id: "t1",
                canonicalName: "Apple",
                per100g: MacroTotals(calories: 52, proteinG: 0, carbsG: 14, fatG: 0),
                ingredientFamily: "fruit"
            )
        )
        try context.save()
        XCTAssertTrue(SeedImporter.searchFoods(query: "", in: context).isEmpty)
        XCTAssertFalse(SeedImporter.searchFoods(query: "app", in: context).isEmpty)
    }
}
