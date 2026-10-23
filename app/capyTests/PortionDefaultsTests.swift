import XCTest
@testable import capy

final class PortionDefaultsTests: XCTestCase {
    func testFatAndEggFallbacks() {
        XCTAssertEqual(
            PortionDefaults.servingGrams(family: "fat", name: "Olive oil", kcalPer100g: 884),
            14,
            accuracy: 0.1
        )
        XCTAssertEqual(
            PortionDefaults.servingGrams(family: "egg", name: "Egg white", kcalPer100g: 52),
            33,
            accuracy: 0.1
        )
        XCTAssertEqual(
            PortionDefaults.servingGrams(family: "egg", name: "Egg, whole", kcalPer100g: 143),
            50,
            accuracy: 0.1
        )
    }

    func testScaledMacros() {
        let per100 = MacroTotals(calories: 100, proteinG: 10, carbsG: 20, fatG: 5)
        let scaled = PortionDefaults.scaledMacros(per100g: per100, grams: 50)
        XCTAssertEqual(scaled.calories, 50, accuracy: 0.01)
        XCTAssertEqual(scaled.proteinG, 5, accuracy: 0.01)
    }
}
