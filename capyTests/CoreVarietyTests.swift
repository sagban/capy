import XCTest
@testable import capy

private struct Candidate: Equatable {
    let id: String
    let family: String
}

final class CoreVarietyTests: XCTestCase {
    func testHardFilterBlocksTodayFamilies() {
        let candidates = [
            Candidate(id: "a", family: "poultry"),
            Candidate(id: "b", family: "grain"),
            Candidate(id: "c", family: "dairy"),
        ]
        let filtered = VarietyFilter.applyHardFilter(
            candidates: candidates,
            familyOf: \.family,
            todayFamilies: ["Poultry", "egg"]
        )
        XCTAssertEqual(filtered.map(\.id), ["b", "c"])
    }

    func testDecayRanksDownNotOut() {
        let candidates = [
            Candidate(id: "rice", family: "grain"),
            Candidate(id: "dal", family: "legume"),
            Candidate(id: "oats", family: "grain"),
        ]
        let days = ["d1", "d2", "d3", "d4", "d5", "d6", "d7"]
        let byDay: [String: Set<String>] = [
            "d1": ["rice"],
            "d2": ["rice"],
            "d3": ["rice"],
            "d4": ["dal"],
            "d5": [],
            "d6": [],
            "d7": [],
        ]
        let ranked = VarietyFilter.rankByDecay(
            candidates: candidates,
            foodIdOf: \.id,
            dayKeysLast7: days,
            foodIdsByDay: byDay
        )
        // rice seen 3 days → penalty; dal/oats stay ahead
        XCTAssertEqual(ranked.map(\.id), ["dal", "oats", "rice"])
        XCTAssertEqual(ranked.count, 3)
    }

    func testFilterAndRankGolden() {
        let candidates = [
            Candidate(id: "chicken", family: "poultry"),
            Candidate(id: "tofu", family: "soy"),
            Candidate(id: "rice", family: "grain"),
        ]
        let ranked = VarietyFilter.filterAndRank(
            candidates: candidates,
            familyOf: \.family,
            foodIdOf: \.id,
            todayFamilies: ["poultry"],
            dayKeysLast7: ["a", "b", "c", "d", "e", "f", "g"],
            foodIdsByDay: [
                "a": ["rice"], "b": ["rice"], "c": ["rice"],
                "d": [], "e": [], "f": [], "g": [],
            ]
        )
        XCTAssertFalse(ranked.contains(where: { $0.id == "chicken" }))
        XCTAssertEqual(ranked.first?.id, "tofu")
        XCTAssertEqual(ranked.last?.id, "rice")
    }
}
