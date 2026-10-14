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

    /// Drop the open confirm draft after the user logs or corrects it.
    static func clearOpenDraft(in context: ModelContext) {
        let turns = orderedTurns(thread(in: context))
        guard let last = turns.last(where: { $0.role == .assistant }),
              let payload = last.structuredPayload,
              let data = payload.data(using: .utf8),
              var decoded = try? JSONDecoder().decode(WorkingMemoryPayload.self, from: data)
        else { return }
        decoded.draftLog = []
        decoded.pendingAction = nil
        decoded.resolveQueue = nil
        decoded.pendingIntent = nil
        if let encoded = try? JSONEncoder().encode(decoded),
           let string = String(data: encoded, encoding: .utf8) {
            last.structuredPayload = string
        }
    }

    static func workingMemory(from thread: ConversationThread) -> WorkingMemoryPayload? {
        guard let lastAssistant = orderedTurns(thread).last(where: { $0.role == .assistant }),
              let payload = lastAssistant.structuredPayload,
              let data = payload.data(using: .utf8),
              let decoded = try? JSONDecoder().decode(WorkingMemoryPayload.self, from: data)
        else {
            return nil
        }
        if decoded.pendingAction != nil
            || decoded.resolveQueue != nil
            || !decoded.lastSuggestionOptions.isEmpty
            || !decoded.draftLog.isEmpty
        {
            return decoded
        }
        guard decoded.pendingIntent == "clarify"
            || (decoded.pendingIntent?.hasPrefix("confirm_") == true)
            || (decoded.pendingIntent?.hasPrefix("clarify_") == true)
            || !decoded.candidates.isEmpty
        else {
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
    var candidates: [WorkingMemoryCandidate]
    var pendingAction: PendingActionDTO?
    var resolveQueue: ResolveQueueDTO?
    var lastSuggestionOptions: [SuggestionOptionDTO]
    var draftLog: [ResolvedItemDTO]

    init(
        pendingIntent: String? = nil,
        clarifyingQuestion: String? = nil,
        candidates: [WorkingMemoryCandidate] = [],
        pendingAction: PendingActionDTO? = nil,
        resolveQueue: ResolveQueueDTO? = nil,
        lastSuggestionOptions: [SuggestionOptionDTO] = [],
        draftLog: [ResolvedItemDTO] = []
    ) {
        self.pendingIntent = pendingIntent
        self.clarifyingQuestion = clarifyingQuestion
        self.candidates = candidates
        self.pendingAction = pendingAction
        self.resolveQueue = resolveQueue
        self.lastSuggestionOptions = lastSuggestionOptions
        self.draftLog = draftLog
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        pendingIntent = try c.decodeIfPresent(String.self, forKey: .pendingIntent)
        clarifyingQuestion = try c.decodeIfPresent(String.self, forKey: .clarifyingQuestion)
        candidates = try c.decodeIfPresent([WorkingMemoryCandidate].self, forKey: .candidates) ?? []
        pendingAction = try c.decodeIfPresent(PendingActionDTO.self, forKey: .pendingAction)
        resolveQueue = try c.decodeIfPresent(ResolveQueueDTO.self, forKey: .resolveQueue)
        lastSuggestionOptions = try c.decodeIfPresent([SuggestionOptionDTO].self, forKey: .lastSuggestionOptions) ?? []
        draftLog = try c.decodeIfPresent([ResolvedItemDTO].self, forKey: .draftLog) ?? []
    }

    private enum CodingKeys: String, CodingKey {
        case pendingIntent, clarifyingQuestion, candidates, pendingAction
        case resolveQueue, lastSuggestionOptions, draftLog
    }
}

struct ResolveQueueDTO: Codable, Equatable {
    var resolved: [ResolvedItemDTO]
    var pending: ItemDraftDTO?
    var remaining: [ItemDraftDTO]
    var committed: CommittedFoodDTO?
    var clarifyOptions: [ClarifyOptionDTO]
    var correctionEntryId: String?
    var correctionItemIndex: Int?
    var correctionOp: String?

    init(
        resolved: [ResolvedItemDTO] = [],
        pending: ItemDraftDTO? = nil,
        remaining: [ItemDraftDTO] = [],
        committed: CommittedFoodDTO? = nil,
        clarifyOptions: [ClarifyOptionDTO] = [],
        correctionEntryId: String? = nil,
        correctionItemIndex: Int? = nil,
        correctionOp: String? = nil
    ) {
        self.resolved = resolved
        self.pending = pending
        self.remaining = remaining
        self.committed = committed
        self.clarifyOptions = clarifyOptions
        self.correctionEntryId = correctionEntryId
        self.correctionItemIndex = correctionItemIndex
        self.correctionOp = correctionOp
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        resolved = try c.decodeIfPresent([ResolvedItemDTO].self, forKey: .resolved) ?? []
        pending = try c.decodeIfPresent(ItemDraftDTO.self, forKey: .pending)
        remaining = try c.decodeIfPresent([ItemDraftDTO].self, forKey: .remaining) ?? []
        committed = try c.decodeIfPresent(CommittedFoodDTO.self, forKey: .committed)
        clarifyOptions = try c.decodeIfPresent([ClarifyOptionDTO].self, forKey: .clarifyOptions) ?? []
        correctionEntryId = try c.decodeIfPresent(String.self, forKey: .correctionEntryId)
        correctionItemIndex = try c.decodeIfPresent(Int.self, forKey: .correctionItemIndex)
        correctionOp = try c.decodeIfPresent(String.self, forKey: .correctionOp)
    }

    private enum CodingKeys: String, CodingKey {
        case resolved, pending, remaining, committed, clarifyOptions
        case correctionEntryId, correctionItemIndex, correctionOp
    }
}

struct ItemDraftDTO: Codable, Equatable {
    var rawText: String?
    var foodQuery: String
    var brandOrVenue: String?
    var quantity: Double?
    var unit: String?
    var aliases: [String]?
}

struct CommittedFoodDTO: Codable, Equatable {
    var foodId: String
    var displayName: String
    var per100g: MacroTotals
    var source: String
    var citationUrl: String?
    var family: String?
    var measures: [HouseholdMeasureDTO]?
}

struct WorkingMemoryCandidate: Codable, Equatable {
    var foodId: String
    var displayName: String
    var grams: Double?
    var source: String?
}
