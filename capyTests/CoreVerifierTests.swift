import XCTest
@testable import capy

final class CoreVerifierTests: XCTestCase {
    private let remaining = MacroTotals(calories: 600, proteinG: 40, carbsG: 60, fatG: 20)

    func testAcceptsWithinBand() {
        let proposed = MacroTotals(calories: 550, proteinG: 40, carbsG: 60, fatG: 20)
        let outcome = SuggestionVerifier.verify(proposed: proposed, remaining: remaining)
        if case .accepted(let totals) = outcome {
            XCTAssertEqual(totals, proposed)
        } else {
            XCTFail("expected accepted, got \(outcome)")
        }
    }

    func testRejectsCaloriesOverRemaining() {
        let proposed = MacroTotals(calories: 700, proteinG: 40, carbsG: 60, fatG: 20)
        let outcome = SuggestionVerifier.verify(proposed: proposed, remaining: remaining)
        if case .rejected(let reason, _) = outcome {
            XCTAssertEqual(reason, .caloriesExceedRemaining)
        } else {
            XCTFail("expected rejected calories, got \(outcome)")
        }
    }

    func testRejectsMacroOutOfBand() {
        let proposed = MacroTotals(calories: 500, proteinG: 10, carbsG: 60, fatG: 20)
        let outcome = SuggestionVerifier.verify(proposed: proposed, remaining: remaining)
        if case .rejected(let reason, _) = outcome {
            XCTAssertEqual(reason, .proteinOutOfBand)
        } else {
            XCTFail("expected protein rejection, got \(outcome)")
        }
    }

    func testRetriesThenAbstain() {
        let bad = MacroTotals(calories: 900, proteinG: 40, carbsG: 60, fatG: 20)
        let outcome = SuggestionVerifier.verifyWithRetries(
            proposals: [bad, bad, bad],
            remaining: remaining,
            maxRetries: 2
        )
        if case .abstain(let reasons) = outcome {
            XCTAssertEqual(reasons.count, 3)
            XCTAssertTrue(reasons.allSatisfy { $0 == .caloriesExceedRemaining })
        } else {
            XCTFail("expected abstain, got \(outcome)")
        }
    }

    func testRetryAcceptsSecondProposal() {
        let bad = MacroTotals(calories: 900, proteinG: 40, carbsG: 60, fatG: 20)
        let good = MacroTotals(calories: 550, proteinG: 40, carbsG: 60, fatG: 20)
        let outcome = SuggestionVerifier.verifyWithRetries(
            proposals: [bad, good],
            remaining: remaining,
            maxRetries: 2
        )
        if case .accepted(let totals) = outcome {
            XCTAssertEqual(totals, good)
        } else {
            XCTFail("expected accepted on retry, got \(outcome)")
        }
    }
}

final class SuggestionFitTests: XCTestCase {
    private let remaining = MacroTotals(calories: 1650, proteinG: 124, carbsG: 165, fatG: 55)

    func testMealSizedFoodFitsBudgetNotWholeDay() {
        let proposed = MacroTotals(calories: 420, proteinG: 35, carbsG: 10, fatG: 8)
        let outcome = SuggestionVerifier.verifyFit(
            proposed: proposed,
            remaining: remaining,
            budget: SuggestionBudget(calories: 500, proteinG: 30)
        )
        XCTAssertEqual(outcome, .accepted(proposed))
    }

    func testRejectsOverStatedCalorieBudget() {
        let proposed = MacroTotals(calories: 700, proteinG: 40, carbsG: 10, fatG: 8)
        let outcome = SuggestionVerifier.verifyFit(
            proposed: proposed,
            remaining: remaining,
            budget: SuggestionBudget(calories: 500, proteinG: 30)
        )
        if case .rejected(let reason, _) = outcome {
            XCTAssertEqual(reason, .caloriesExceedRemaining)
        } else {
            XCTFail("expected rejection, got \(outcome)")
        }
    }

    func testSmallerMealIsStillWithin() {
        let proposed = MacroTotals(calories: 350, proteinG: 30, carbsG: 80, fatG: 40)
        let outcome = SuggestionVerifier.verifyFit(
            proposed: proposed,
            remaining: remaining,
            budget: SuggestionBudget(calories: 700, proteinG: 20)
        )
        XCTAssertEqual(outcome, .accepted(proposed))
    }

    func testSmallerMealStaysWithinWhenProteinIsShort() {
        let proposed = MacroTotals(calories: 300, proteinG: 10, carbsG: 30, fatG: 5)
        let outcome = SuggestionVerifier.verifyFit(
            proposed: proposed,
            remaining: remaining,
            budget: SuggestionBudget(calories: 500, proteinG: 30)
        )
        XCTAssertEqual(outcome, .accepted(proposed))
    }
}
