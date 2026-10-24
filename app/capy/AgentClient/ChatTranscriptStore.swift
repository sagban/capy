import Foundation
import SwiftData

/// Local copy of the Capy thread so the chat is still there with no network.
@MainActor
enum ChatTranscriptStore {
    struct Page {
        var bubbles: [ChatBubble]
        var hasMore: Bool
    }

    private static let legacyOpener = "what did you have to eat?"
    private static let pendingSeq = -1

    static func all(threadId: String, in context: ModelContext) -> [ChatBubble] {
        ordered(threadId: threadId, in: context).compactMap(bubble(from:))
    }

    static func latest(threadId: String, limit: Int, in context: ModelContext) -> Page {
        let rows = ordered(threadId: threadId, in: context)
        let tail = Array(rows.suffix(max(limit, 1)))
        return Page(bubbles: tail.compactMap(bubble(from:)), hasMore: rows.count > tail.count)
    }

    static func older(before messageId: String, threadId: String, limit: Int, in context: ModelContext) -> Page {
        let rows = ordered(threadId: threadId, in: context)
        guard let index = rows.firstIndex(where: { $0.messageId == messageId }), index > 0 else {
            return Page(bubbles: [], hasMore: false)
        }
        let start = max(0, index - max(limit, 1))
        let slice = Array(rows[start..<index])
        return Page(bubbles: slice.compactMap(bubble(from:)), hasMore: start > 0)
    }

    static func hasOlder(before messageId: String?, threadId: String, in context: ModelContext) -> Bool {
        guard let messageId else { return false }
        let rows = ordered(threadId: threadId, in: context)
        guard let index = rows.firstIndex(where: { $0.messageId == messageId }) else { return false }
        return index > 0
    }

    static func pending(threadId: String, in context: ModelContext) -> [ChatBubble] {
        ordered(threadId: threadId, in: context)
            .filter { $0.seq < 0 }
            .compactMap(bubble(from:))
    }

    static func upsert(messages: [ThreadMessageDTO], threadId: String, in context: ModelContext) {
        for message in messages {
            let text = message.text
            let role = roleRaw(from: message.role)
            if role != "user" && text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { continue }
            if role != "user" && text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() == legacyOpener { continue }
            let record = fetch(messageId: message.messageId, in: context) ?? ChatMessageRecord(
                messageId: message.messageId,
                threadId: threadId,
                roleRaw: role,
                text: text,
                createdAt: parseDate(message.createdAt),
                seq: message.seq ?? pendingSeq
            )
            record.threadId = threadId
            record.roleRaw = role
            record.text = text
            record.createdAt = parseDate(message.createdAt)
            if let seq = message.seq {
                record.seq = seq
            }
            if record.modelContext == nil {
                context.insert(record)
            }
        }
        try? context.save()
    }

    static func upsert(_ bubble: ChatBubble, threadId: String, in context: ModelContext) {
        guard bubble.role != .error else { return }
        let text = bubble.text
        if bubble.role != .user && text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return }
        let record = fetch(messageId: bubble.id, in: context) ?? ChatMessageRecord(
            messageId: bubble.id,
            threadId: threadId,
            roleRaw: bubble.role == .user ? "user" : "capy",
            text: text,
            createdAt: .now,
            seq: pendingSeq,
            manualLog: bubble.manualLog,
            freeTextGrams: bubble.freeTextGrams
        )
        record.threadId = threadId
        record.roleRaw = bubble.role == .user ? "user" : "capy"
        record.text = text
        record.manualLog = bubble.manualLog
        record.freeTextGrams = bubble.freeTextGrams
        if record.modelContext == nil {
            context.insert(record)
        }
        try? context.save()
    }

    /// Drop phone-only copies once the same text arrived from the server under its archive id.
    static func absorbOptimisticDuplicates(matching messages: [ThreadMessageDTO], threadId: String, in context: ModelContext) {
        var pending = ordered(threadId: threadId, in: context).filter { $0.seq < 0 }
        var changed = false
        for message in messages {
            let role = roleRaw(from: message.role)
            let text = message.text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard let index = pending.firstIndex(where: {
                $0.roleRaw == role && $0.text.trimmingCharacters(in: .whitespacesAndNewlines) == text
            }) else { continue }
            context.delete(pending.remove(at: index))
            changed = true
        }
        if changed { try? context.save() }
    }

    static func clear(threadId: String, in context: ModelContext) {
        let threadId = threadId
        let descriptor = FetchDescriptor<ChatMessageRecord>(
            predicate: #Predicate { $0.threadId == threadId }
        )
        let rows = (try? context.fetch(descriptor)) ?? []
        for row in rows { context.delete(row) }
        if !rows.isEmpty { try? context.save() }
    }

    /// Chats saved before the transcript was tied to an account. They have no uid in `threadId`.
    static func discardLegacyUnscoped(in context: ModelContext) {
        let descriptor = FetchDescriptor<ChatMessageRecord>()
        let rows = (try? context.fetch(descriptor)) ?? []
        let stale = rows.filter { !$0.threadId.contains("|") }
        for row in stale { context.delete(row) }
        if !stale.isEmpty { try? context.save() }
    }

    static func storageKey(uid: String, threadId: String = CapyThreadService.defaultThreadId) -> String {
        "\(uid)|\(threadId)"
    }

    private static func ordered(threadId: String, in context: ModelContext) -> [ChatMessageRecord] {
        let threadId = threadId
        let descriptor = FetchDescriptor<ChatMessageRecord>(
            predicate: #Predicate { $0.threadId == threadId }
        )
        let rows = (try? context.fetch(descriptor)) ?? []
        let archived = rows.filter { $0.seq >= 0 }.sorted { $0.seq < $1.seq }
        let pending = rows.filter { $0.seq < 0 }.sorted { $0.createdAt < $1.createdAt }
        return archived + pending
    }

    private static func fetch(messageId: String, in context: ModelContext) -> ChatMessageRecord? {
        let messageId = messageId
        var descriptor = FetchDescriptor<ChatMessageRecord>(
            predicate: #Predicate { $0.messageId == messageId }
        )
        descriptor.fetchLimit = 1
        return try? context.fetch(descriptor).first
    }

    private static func bubble(from record: ChatMessageRecord) -> ChatBubble? {
        let text = record.text.trimmingCharacters(in: .whitespacesAndNewlines)
        let role: ChatBubble.Role = record.roleRaw == "user" ? .user : .capy
        if role != .user && text.isEmpty { return nil }
        if role != .user && text.lowercased() == legacyOpener { return nil }
        return ChatBubble(
            serverMessageId: record.messageId,
            role: role,
            text: record.text,
            manualLog: record.manualLog,
            freeTextGrams: record.freeTextGrams
        )
    }

    private static func roleRaw(from serverRole: String) -> String {
        serverRole.lowercased() == "user" ? "user" : "capy"
    }

    private static func parseDate(_ raw: String?) -> Date {
        guard let raw, !raw.isEmpty else { return .now }
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = fractional.date(from: raw) { return date }
        let plain = ISO8601DateFormatter()
        plain.formatOptions = [.withInternetDateTime]
        return plain.date(from: raw) ?? .now
    }
}
