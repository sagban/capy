import Foundation

struct WorkingMemoryPayload: Codable, Equatable, Sendable {
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

struct ResolveQueueDTO: Codable, Equatable, Sendable {
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

struct ItemDraftDTO: Codable, Equatable, Sendable {
    var rawText: String?
    var foodQuery: String
    var brandOrVenue: String?
    var quantity: Double?
    var unit: String?
    var aliases: [String]?
}

struct CommittedFoodDTO: Codable, Equatable, Sendable {
    var foodId: String
    var displayName: String
    var per100g: MacroTotals
    var source: String
    var citationUrl: String?
    var family: String?
    var measures: [HouseholdMeasureDTO]?
}

struct WorkingMemoryCandidate: Codable, Equatable, Sendable {
    var foodId: String
    var displayName: String
    var grams: Double?
    var source: String?
}
