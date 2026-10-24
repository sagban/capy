import Foundation
import SwiftData

/// One chat bubble stored on the phone. `seq` matches the server archive; `-1` is a message not on the server yet.
@Model
final class ChatMessageRecord {
    @Attribute(.unique) var messageId: String
    var threadId: String
    var roleRaw: String
    var text: String
    var createdAt: Date
    var seq: Int
    var manualLog: Bool
    var freeTextGrams: Bool

    init(
        messageId: String,
        threadId: String,
        roleRaw: String,
        text: String,
        createdAt: Date,
        seq: Int,
        manualLog: Bool = false,
        freeTextGrams: Bool = false
    ) {
        self.messageId = messageId
        self.threadId = threadId
        self.roleRaw = roleRaw
        self.text = text
        self.createdAt = createdAt
        self.seq = seq
        self.manualLog = manualLog
        self.freeTextGrams = freeTextGrams
    }
}
