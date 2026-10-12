import Foundation
import SwiftData

@Model
final class ConversationThread {
    @Attribute(.unique) var id: String
    var summary: String
    var updatedAt: Date
    @Relationship(deleteRule: .cascade, inverse: \ConversationTurn.thread)
    var turns: [ConversationTurn]

    init(
        id: String = "default",
        summary: String = "",
        updatedAt: Date = .now,
        turns: [ConversationTurn] = []
    ) {
        self.id = id
        self.summary = summary
        self.updatedAt = updatedAt
        self.turns = turns
    }
}

@Model
final class ConversationTurn {
    var id: UUID
    var roleRaw: String
    var text: String
    var createdAt: Date
    /// Optional JSON blob for structured payload (intent, candidates, clarify).
    var structuredPayload: String?
    var thread: ConversationThread?
    /// Soft-delete flag used while SwiftData finishes cascading relationship cleanup.
    var isDeleted: Bool = false

    var role: ConversationRole {
        get { ConversationRole(rawValue: roleRaw) ?? .user }
        set { roleRaw = newValue.rawValue }
    }

    init(
        id: UUID = UUID(),
        role: ConversationRole,
        text: String,
        createdAt: Date = .now,
        structuredPayload: String? = nil
    ) {
        self.id = id
        self.roleRaw = role.rawValue
        self.text = text
        self.createdAt = createdAt
        self.structuredPayload = structuredPayload
        self.isDeleted = false
    }
}

enum ConversationRole: String, Codable {
    case user
    case assistant
}

enum LongTermMemorySource: String, Codable {
    case user
    case agent
}

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
