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
    }
}
