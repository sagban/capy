import Foundation
import SwiftData

@Model
final class LongTermMemoryNote {
    @Attribute(.unique) var id: String
    var text: String
    var createdAt: Date
    var updatedAt: Date
    var sourceRaw: String

    var source: LongTermMemorySource {
        get { LongTermMemorySource(rawValue: sourceRaw) ?? .user }
        set { sourceRaw = newValue.rawValue }
    }

    init(
        id: String = UUID().uuidString,
        text: String,
        createdAt: Date = .now,
        updatedAt: Date = .now,
        source: LongTermMemorySource = .user
    ) {
        self.id = id
        self.text = text
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.sourceRaw = source.rawValue
    }
}
