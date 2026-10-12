import Foundation
import SwiftData

/// Single long-running Capy thread: turns + rolling summary + working slot rebuild.
enum ConversationMemoryStore {
    static let windowSize = 12
    static let threadId = "default"

    static func thread(in context: ModelContext) -> ConversationThread {
        var descriptor = FetchDescriptor<ConversationThread>(
            predicate: #Predicate { $0.id == threadId }
        )
        descriptor.fetchLimit = 1
        if let existing = try? context.fetch(descriptor).first {
            return existing
        }
        let created = ConversationThread(id: threadId)
        context.insert(created)
        return created
    }

    static func appendTurn(
        role: ConversationRole,
        text: String,
        structuredPayload: String? = nil,
        in context: ModelContext
    ) {
        let t = thread(in: context)
        let prior = orderedTurns(t)
        // Stagger timestamps so same-second appends stay ordered for trim/window.
        let createdAt = prior.last.map { $0.createdAt.addingTimeInterval(0.001) } ?? Date()
        let turn = ConversationTurn(
            role: role,
            text: text,
            createdAt: createdAt,
            structuredPayload: structuredPayload
        )
        turn.thread = t
        t.turns.append(turn)
        t.updatedAt = Date()
        trimIfNeeded(thread: t, in: context)
    }

    static func orderedTurns(_ thread: ConversationThread) -> [ConversationTurn] {
        thread.turns
            .filter { !$0.isDeleted }
            .sorted { lhs, rhs in
                if lhs.createdAt != rhs.createdAt { return lhs.createdAt < rhs.createdAt }
                return lhs.id.uuidString < rhs.id.uuidString
            }
    }

    static func recentTurns(_ thread: ConversationThread, limit: Int = windowSize) -> [ConversationTurn] {
        Array(orderedTurns(thread).suffix(limit))
    }

    /// When over window, fold oldest into summary (rule-based, no invented macros).
    static func trimIfNeeded(thread: ConversationThread, in context: ModelContext) {
        let ordered = orderedTurns(thread)
        guard ordered.count > windowSize else { return }
        let overflow = ordered.prefix(ordered.count - windowSize)
        let folded = overflow.map { turn in
            let label = turn.role == .user ? "user" : "capy"
            return "\(label): \(compact(turn.text))"
        }
        .joined(separator: " · ")
        if thread.summary.isEmpty {
            thread.summary = folded
        } else {
            thread.summary = compact(thread.summary + " · " + folded)
        }
        if thread.summary.count > 1200 {
            thread.summary = String(thread.summary.suffix(1200))
        }
        for turn in overflow {
            turn.isDeleted = true
            if let idx = thread.turns.firstIndex(where: { $0.id == turn.id }) {
                thread.turns.remove(at: idx)
            }
            context.delete(turn)
        }
        thread.updatedAt = Date()
    }

    static func workingMemory(from thread: ConversationThread) -> WorkingMemoryPayload? {
        guard let lastAssistant = orderedTurns(thread).last(where: { $0.role == .assistant }),
              let payload = lastAssistant.structuredPayload,
              let data = payload.data(using: .utf8),
              let decoded = try? JSONDecoder().decode(WorkingMemoryPayload.self, from: data)
        else {
            return nil
        }
        guard decoded.pendingIntent == "clarify" || !(decoded.candidates ?? []).isEmpty else {
            return nil
        }
        return decoded
    }

    static func noteDayRollover(previousDayKey: String, mealCount: Int, in context: ModelContext) {
        let t = thread(in: context)
        let note = "new day — prior day \(previousDayKey) logged \(mealCount) meals"
        if t.summary.isEmpty {
            t.summary = note
        } else if !t.summary.contains(note) {
            t.summary = compact(t.summary + " · " + note)
        }
        t.updatedAt = .now
    }

    private static func compact(_ text: String) -> String {
        text
            .replacingOccurrences(of: "\n", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

struct WorkingMemoryPayload: Codable, Equatable {
    var pendingIntent: String?
    var clarifyingQuestion: String?
    var candidates: [WorkingMemoryCandidate]?
}

struct WorkingMemoryCandidate: Codable, Equatable {
    var foodId: String
    var displayName: String
    var grams: Double?
}
