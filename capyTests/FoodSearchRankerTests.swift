import XCTest
@testable import capy

final class FoodSearchRankerTests: XCTestCase {
    private struct Hit {
        var id: String
        var name: String
        var aliases: [String] = []
        var family: String = "grain"
    }

    func testRiceRanksCookedStapleAboveBabyfood() {
        let hits = [
            Hit(id: "usda_sake", name: "Alcoholic beverage, rice (sake)"),
            Hit(id: "usda_baby", name: "Babyfood, cereal, rice, dry fortified"),
            Hit(id: "usda_168878", name: "Rice, white, long-grain, regular, enriched, cooked"),
            Hit(id: "usda_raw", name: "Rice, white, long-grain, regular, raw, enriched"),
            Hit(id: "usda_mix", name: "Rice and vermicelli mix, chicken flavor, unprepared"),
        ]
        let ranked = FoodSearchRanker.ranked(
            hits,
            query: "rice",
            name: \.name,
            aliases: \.aliases,
            family: \.family,
            foodId: \.id,
            limit: 5
        )
        XCTAssertEqual(ranked.first?.id, "usda_168878")
        XCTAssertFalse(ranked.prefix(3).contains(where: { $0.id == "usda_baby" || $0.id == "usda_sake" }))
    }

    func testShortQueryHiDoesNotMatchChicken() {
        XCTAssertFalse(
            FoodSearchRanker.shortQueryMatches(
                query: "hi",
                name: "Chicken, broilers or fryers, breast, meat only, cooked, roasted",
                aliases: []
            )
        )
        XCTAssertFalse(
            FoodSearchRanker.shortQueryMatches(
                query: "hi",
                name: "Rice, white, long-grain, regular, enriched, cooked",
                aliases: []
            )
        )
    }

    func testAliasExactBeatsSubstringNoise() {
        let hits = [
            Hit(id: "noise", name: "Beef, chuck, shoulder clod, shoulder tender, medallion"),
            Hit(id: "seed_dal", name: "Dal (cooked lentils)", aliases: ["dal"], family: "legume"),
        ]
        let ranked = FoodSearchRanker.ranked(
            hits,
            query: "dal",
            name: \.name,
            aliases: \.aliases,
            family: \.family,
            foodId: \.id,
            limit: 2
        )
        XCTAssertEqual(ranked.first?.id, "seed_dal")
    }
}
