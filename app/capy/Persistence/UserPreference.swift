import Foundation
import SwiftData

@Model
final class UserPreference {
    var kindRaw: String
    var value: String
    var createdAt: Date

    var kind: PreferenceKind {
        get { PreferenceKind(rawValue: kindRaw) ?? .like }
        set { kindRaw = newValue.rawValue }
    }

    init(kind: PreferenceKind, value: String, createdAt: Date = .now) {
        self.kindRaw = kind.rawValue
        self.value = value
        self.createdAt = createdAt
    }
}
