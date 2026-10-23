import XCTest
@testable import capy

final class CoreRemainingTests: XCTestCase {
    func testRemainingClampsAtZero() {
        let target = MacroTotals(calories: 2000, proteinG: 140, carbsG: 200, fatG: 65)
        let eaten = MacroTotals(calories: 2500, proteinG: 100, carbsG: 250, fatG: 40)
        let remaining = MacroTotals.remaining(target: target, eaten: eaten)
        XCTAssertEqual(remaining.calories, 0)
        XCTAssertEqual(remaining.proteinG, 40)
        XCTAssertEqual(remaining.carbsG, 0)
        XCTAssertEqual(remaining.fatG, 25)
    }

    func testRemainingNeverNegative() {
        let target = MacroTotals(calories: 100, proteinG: 10, carbsG: 10, fatG: 10)
        let eaten = MacroTotals(calories: 999, proteinG: 999, carbsG: 999, fatG: 999)
        let remaining = MacroTotals.remaining(target: target, eaten: eaten)
        XCTAssertGreaterThanOrEqual(remaining.calories, 0)
        XCTAssertGreaterThanOrEqual(remaining.proteinG, 0)
        XCTAssertGreaterThanOrEqual(remaining.carbsG, 0)
        XCTAssertGreaterThanOrEqual(remaining.fatG, 0)
    }

    func testIsOverBudgetWhenAnyMacroExceeds() {
        let target = MacroTotals(calories: 2000, proteinG: 140, carbsG: 200, fatG: 65)
        let eaten = MacroTotals(calories: 2100, proteinG: 100, carbsG: 100, fatG: 40)
        XCTAssertTrue(MacroTotals.isOverBudget(target: target, eaten: eaten))
        XCTAssertNotNil(MacroTotals.overBudgetNote(target: target, eaten: eaten))
    }

    func testDisplayRoundingDoesNotFeedCalc() {
        // Calc uses full precision; Int display of 99.6 must not become 100 in math.
        let per100 = MacroTotals(calories: 165, proteinG: 31, carbsG: 0, fatG: 3.6)
        let scaled = MacroMath.scale(per100g: per100, grams: 123.4)
        let displayCalories = Double(Int(scaled.calories.rounded()))
        XCTAssertNotEqual(scaled.calories, displayCalories)
        let target = MacroTotals(calories: 2000, proteinG: 140, carbsG: 200, fatG: 65)
        let remainingFromRaw = MacroTotals.remaining(target: target, eaten: scaled)
        let remainingFromRounded = MacroTotals.remaining(
            target: target,
            eaten: MacroTotals(calories: displayCalories, proteinG: scaled.proteinG, carbsG: scaled.carbsG, fatG: scaled.fatG)
        )
        // Documented rule: prefer raw for calc — values can diverge when rounding.
        XCTAssertNotEqual(remainingFromRaw.calories, remainingFromRounded.calories)
    }

    func testScalePer100g() {
        let per100 = MacroTotals(calories: 100, proteinG: 10, carbsG: 20, fatG: 5)
        let half = MacroMath.scale(per100g: per100, grams: 50)
        XCTAssertEqual(half.calories, 50)
        XCTAssertEqual(half.proteinG, 5)
        XCTAssertEqual(half.carbsG, 10)
        XCTAssertEqual(half.fatG, 2.5)
    }
}
