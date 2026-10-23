import Foundation
import SwiftData

@Model
final class SearchCacheEntry {
    @Attribute(.unique) var normalizedQuery: String
    var dayKey: String
    var resultFoodIdsRaw: String
    var isMiss: Bool
    var createdAt: Date

    var resultFoodIds: [String] {
        get {
            resultFoodIdsRaw.split(separator: "|").map(String.init).filter { !$0.isEmpty }
        }
        set {
            resultFoodIdsRaw = newValue.joined(separator: "|")
        }
    }

    init(
        normalizedQuery: String,
        dayKey: String,
        resultFoodIds: [String],
        isMiss: Bool,
        createdAt: Date = .now
    ) {
        self.normalizedQuery = normalizedQuery
        self.dayKey = dayKey
        self.resultFoodIdsRaw = resultFoodIds.joined(separator: "|")
        self.isMiss = isMiss
        self.createdAt = createdAt
    }
}
