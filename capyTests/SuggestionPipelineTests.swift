import XCTest
@testable import capy

final class SuggestionPipelineTests: XCTestCase {
    private let remaining = MacroTotals(calories: 600, proteinG: 40, carbsG: 60, fatG: 20)

    private func candidate(
        id: String,
        family: String,
        caloriesPer100: Double,
        protein: Double = 40,
        carbs: Double = 60,
        fat: Double = 20,
        grams: Double = 100
    ) -> PipelineCandidate {
        PipelineCandidate(
            foodId: id,
            displayName: id,
            ingredientFamily: family,
            grams: grams,
            per100g: MacroTotals(
                calories: caloriesPer100,
                proteinG: protein,
                carbsG: carbs,
                fatG: fat
            )
        )
    }

    func testAcceptsFittingCandidate() {
        let outcome = SuggestionPipeline.run(
            candidates: [
                candidate(id: "a", family: "grain", caloriesPer100: 550),
            ],
            remaining: remaining,
            todayFamilies: [],
            dayKeysLast7: [],
            foodIdsByDay: [:]
        )
        if case .accepted(let c) = outcome {
            XCTAssertEqual(c.foodId, "a")
        } else {
            XCTFail("expected accepted, got \(outcome)")
        }
    }

    func testHardBlocksTodayFamily() {
        let outcome = SuggestionPipeline.run(
            candidates: [
                candidate(id: "rice", family: "grain", caloriesPer100: 550),
            ],
            remaining: remaining,
            todayFamilies: ["grain"],
            dayKeysLast7: [],
            foodIdsByDay: [:]
        )
        if case .abstain = outcome {
            // ok
        } else {
            XCTFail("expected abstain when family hard-blocked, got \(outcome)")
        }
    }

    func testAbstainsWhenCaloriesExceed() {
        let outcome = SuggestionPipeline.run(
            candidates: [
                candidate(id: "big", family: "grain", caloriesPer100: 900),
                candidate(id: "big2", family: "dairy", caloriesPer100: 950),
                candidate(id: "big3", family: "legume", caloriesPer100: 1000),
            ],
            remaining: remaining,
            todayFamilies: [],
            dayKeysLast7: [],
            foodIdsByDay: [:]
        )
        if case .abstain(let reasons) = outcome {
            XCTAssertFalse(reasons.isEmpty)
        } else {
            XCTFail("expected abstain, got \(outcome)")
        }
    }

    func testExcludingFoodIdSkipsCurrent() {
        let outcome = SuggestionPipeline.run(
            candidates: [
                candidate(id: "first", family: "grain", caloriesPer100: 550),
                candidate(id: "second", family: "dairy", caloriesPer100: 560),
            ],
            remaining: remaining,
            todayFamilies: [],
            dayKeysLast7: [],
            foodIdsByDay: [:],
            excludingFoodIds: ["first"]
        )
        if case .accepted(let c) = outcome {
            XCTAssertEqual(c.foodId, "second")
        } else {
            XCTFail("expected second candidate, got \(outcome)")
        }
    }

    func testRetriesThenAcceptsSecond() {
        let outcome = SuggestionPipeline.run(
            candidates: [
                candidate(id: "bad", family: "grain", caloriesPer100: 900),
                candidate(id: "good", family: "dairy", caloriesPer100: 550),
            ],
            remaining: remaining,
            todayFamilies: [],
            dayKeysLast7: [],
            foodIdsByDay: [:]
        )
        if case .accepted(let c) = outcome {
            XCTAssertEqual(c.foodId, "good")
        } else {
            XCTFail("expected good candidate after retry, got \(outcome)")
        }
    }
}
