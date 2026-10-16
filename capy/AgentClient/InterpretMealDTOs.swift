import Foundation

// MARK: - Shared enums (api-contracts)

enum MealIntent: String, Codable, Equatable, Sendable {
    case logMeal = "log_meal"
    case suggestMeal = "suggest_meal"
    case correctMeal = "correct_meal"
    case clarify
    case updatePreference = "update_preference"
    case updateMemory = "update_memory"
    case unknown
}

enum PendingActionType: String, Codable, Equatable, Sendable {
    case clarifyPortion = "clarify_portion"
    case clarifyFood = "clarify_food"
    case confirmLog = "confirm_log"
    case confirmCorrection = "confirm_correction"
    case confirmDelete = "confirm_delete"
}

enum MemoryProposalAction: String, Codable, Equatable, Sendable {
    case add
    case update
    case delete
}

// MARK: - Request DTO

struct InterpretMealRequestDTO: Codable, Equatable, Sendable {
    var utterance: String
    var timezone: String
    var dayKey: String
    var preferenceContext: PreferenceContextDTO = .empty
    var diaryContext: DiaryContextDTO = .empty
    var longTermMemory: [LongTermMemoryNoteDTO] = []
    var conversation: ConversationContextDTO = ConversationContextDTO(summary: "", recentTurns: [])
    var context: InterpretContextDTO = InterpretContextDTO(
        assistanceLevel: "fullAssist",
        responseStyle: "balanced",
        lastIntent: nil
    )
    /// Legacy alias for #37 memory snapshot contract coverage.
    var memorySnapshot: MemorySnapshotDTO?
    /// Optional Capy thread id (`users/{uid}/threads/{threadId}`).
    var threadId: String = CapyThreadService.defaultThreadId
    /// When true, the server loads diary/profile/thread from Firestore (`context_loader`).
    var useServerContext: Bool = true

    enum CodingKeys: String, CodingKey {
        case utterance, timezone, dayKey, threadId, preferenceContext, diaryContext, longTermMemory
        case conversation, context, memorySnapshot, useServerContext
    }

    init(
        utterance: String,
        timezone: String,
        dayKey: String,
        preferenceContext: PreferenceContextDTO = .empty,
        diaryContext: DiaryContextDTO = .empty,
        longTermMemory: [LongTermMemoryNoteDTO] = [],
        conversation: ConversationContextDTO = ConversationContextDTO(summary: "", recentTurns: []),
        context: InterpretContextDTO = InterpretContextDTO(
            assistanceLevel: "fullAssist",
            responseStyle: "balanced",
            lastIntent: nil
        ),
        memorySnapshot: MemorySnapshotDTO? = nil,
        threadId: String = CapyThreadService.defaultThreadId,
        useServerContext: Bool = true
    ) {
        self.utterance = utterance
        self.timezone = timezone
        self.dayKey = dayKey
        self.preferenceContext = preferenceContext
        self.diaryContext = diaryContext
        self.longTermMemory = longTermMemory
        self.conversation = conversation
        self.context = context
        self.memorySnapshot = memorySnapshot
        self.threadId = threadId
        self.useServerContext = useServerContext
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(utterance, forKey: .utterance)
        try container.encode(timezone, forKey: .timezone)
        try container.encode(dayKey, forKey: .dayKey)
        if useServerContext {
            try container.encode(true, forKey: .useServerContext)
            if threadId != CapyThreadService.defaultThreadId {
                try container.encode(threadId, forKey: .threadId)
            }
            return
        }
        try container.encode(preferenceContext, forKey: .preferenceContext)
        try container.encode(diaryContext, forKey: .diaryContext)
        try container.encode(longTermMemory, forKey: .longTermMemory)
        try container.encode(conversation, forKey: .conversation)
        try container.encode(context, forKey: .context)
        try container.encodeIfPresent(memorySnapshot, forKey: .memorySnapshot)
        try container.encode(useServerContext, forKey: .useServerContext)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        utterance = try container.decode(String.self, forKey: .utterance)
        timezone = try container.decodeIfPresent(String.self, forKey: .timezone) ?? "UTC"
        dayKey = try container.decode(String.self, forKey: .dayKey)
        preferenceContext = try container.decodeIfPresent(PreferenceContextDTO.self, forKey: .preferenceContext) ?? .empty
        diaryContext = try container.decodeIfPresent(DiaryContextDTO.self, forKey: .diaryContext) ?? .empty
        longTermMemory = try container.decodeIfPresent([LongTermMemoryNoteDTO].self, forKey: .longTermMemory) ?? []
        conversation = try container.decodeIfPresent(ConversationContextDTO.self, forKey: .conversation)
            ?? ConversationContextDTO(summary: "", recentTurns: [])
        context = try container.decodeIfPresent(InterpretContextDTO.self, forKey: .context)
            ?? InterpretContextDTO(assistanceLevel: "fullAssist", responseStyle: "balanced", lastIntent: nil)
        memorySnapshot = try container.decodeIfPresent(MemorySnapshotDTO.self, forKey: .memorySnapshot)
        threadId = try container.decodeIfPresent(String.self, forKey: .threadId) ?? CapyThreadService.defaultThreadId
        useServerContext = try container.decodeIfPresent(Bool.self, forKey: .useServerContext) ?? false
    }
}

struct PreferenceContextDTO: Codable, Equatable, Sendable {
    var likes: [String]
    var dislikes: [String]
    var allergies: [String]
    var diets: [String]

    static let empty = PreferenceContextDTO(likes: [], dislikes: [], allergies: [], diets: [])
}

struct DiaryDaySummaryDTO: Codable, Equatable, Sendable {
    var dayKey: String
    var mealCount: Int
    var itemNames: [String]
    /// Per-item name, slot, grams — lets the agent repeat "same as yesterday".
    var entries: [DiaryEntryDTO] = []
}

struct DiaryEntryDTO: Codable, Equatable, Sendable {
    var name: String
    var mealSlot: String?
    var grams: Double?
    var entryId: String? = nil
    var itemIndex: Int? = nil
    var foodId: String? = nil
    var source: String? = nil
    var per100g: MacroTotals? = nil
    var ingredientFamily: String? = nil
}

struct MealPlanSlotDTO: Codable, Equatable, Sendable {
    var name: String
    var sortOrder: Int
    var enabled: Bool
}

struct DiaryContextDTO: Codable, Equatable, Sendable {
    var today: [DiaryEntryDTO]
    var previousDays: [DiaryDaySummaryDTO]
    var remaining: MacroTotals
    var remainingSource: String
    /// Enabled meal types in order (user plan for the day).
    var mealPlan: [MealPlanSlotDTO] = []

    static let empty = DiaryContextDTO(
        today: [],
        previousDays: [],
        remaining: .zero,
        remainingSource: "serverComputed",
        mealPlan: []
    )
}

struct LongTermMemoryNoteDTO: Codable, Equatable, Sendable {
    var id: String
    var text: String
}

struct ConversationTurnDTO: Codable, Equatable, Sendable {
    var role: String
    var text: String
}

struct ConversationContextDTO: Codable, Equatable, Sendable {
    var threadId: String = "default"
    var summary: String = ""
    var recentTurns: [ConversationTurnDTO] = []
    var workingMemory: WorkingMemoryPayload?

    init(
        threadId: String = CapyThreadService.defaultThreadId,
        summary: String = "",
        recentTurns: [ConversationTurnDTO] = [],
        workingMemory: WorkingMemoryPayload? = nil
    ) {
        self.threadId = threadId
        self.summary = summary
        self.recentTurns = recentTurns
        self.workingMemory = workingMemory
    }
}

struct ThreadMessageDTO: Codable, Equatable, Sendable {
    var messageId: String
    var role: String
    var text: String
    var createdAt: String?
}

struct ThreadPageInfoDTO: Codable, Equatable, Sendable {
    var hasMore: Bool
    var nextCursor: String?

    init(hasMore: Bool = false, nextCursor: String? = nil) {
        self.hasMore = hasMore
        self.nextCursor = nextCursor
    }
}

struct GetThreadResponseDTO: Codable, Equatable, Sendable {
    var conversation: ConversationContextDTO
    var messages: [ThreadMessageDTO]
    var pageInfo: ThreadPageInfoDTO
}

struct InterpretContextDTO: Codable, Equatable, Sendable {
    var assistanceLevel: String
    var responseStyle: String
    var lastIntent: String?

    init(assistanceLevel: String, responseStyle: String = "balanced", lastIntent: String?) {
        self.assistanceLevel = assistanceLevel
        self.responseStyle = responseStyle
        self.lastIntent = lastIntent
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        assistanceLevel = try container.decode(String.self, forKey: .assistanceLevel)
        responseStyle = try container.decodeIfPresent(String.self, forKey: .responseStyle) ?? "balanced"
        lastIntent = try container.decodeIfPresent(String.self, forKey: .lastIntent)
    }

    private enum CodingKeys: String, CodingKey {
        case assistanceLevel, responseStyle, lastIntent
    }
}

struct MemorySnapshotDTO: Codable, Equatable, Sendable {
    var preferences: [String]
    var dislikes: [String]
    var allergies: [String]
    var diets: [String]
    var regularTemplateIds: [String]
    var recentCorrections: [RecentCorrectionDTO]
}

struct RecentCorrectionDTO: Codable, Equatable, Sendable {
    var text: String
    var at: String
}

// MARK: - Response DTO

struct InterpretMealResponseDTO: Codable, Equatable, Sendable {
    var intent: MealIntent
    var candidates: [FoodCandidateDTO]
    var clarifyingQuestion: String?
    var correction: String?
    var suggestedTemplateId: String?
    var assistantMessage: String
    var warnings: [String]
    var memoryProposals: [MemoryProposalDTO]?
    var pendingAction: PendingActionDTO?
    var suggestionBudget: SuggestionBudgetDTO?
    var suggestionOptions: [SuggestionOptionDTO]?
    var workingMemory: WorkingMemoryPayload?
    var conversation: ConversationContextDTO?
    var messages: [ThreadMessageDTO]?
    var pageInfo: ThreadPageInfoDTO?

    init(
        intent: MealIntent,
        candidates: [FoodCandidateDTO] = [],
        clarifyingQuestion: String? = nil,
        correction: String? = nil,
        suggestedTemplateId: String? = nil,
        assistantMessage: String,
        warnings: [String] = [],
        memoryProposals: [MemoryProposalDTO]? = nil,
        pendingAction: PendingActionDTO? = nil,
        suggestionBudget: SuggestionBudgetDTO? = nil,
        suggestionOptions: [SuggestionOptionDTO]? = nil,
        workingMemory: WorkingMemoryPayload? = nil,
        conversation: ConversationContextDTO? = nil,
        messages: [ThreadMessageDTO]? = nil,
        pageInfo: ThreadPageInfoDTO? = nil
    ) {
        self.suggestionBudget = suggestionBudget
        self.suggestionOptions = suggestionOptions
        self.workingMemory = workingMemory
        self.conversation = conversation
        self.messages = messages
        self.pageInfo = pageInfo
        self.intent = intent
        self.candidates = candidates
        self.clarifyingQuestion = clarifyingQuestion
        self.correction = correction
        self.suggestedTemplateId = suggestedTemplateId
        self.assistantMessage = assistantMessage
        self.warnings = warnings
        self.memoryProposals = memoryProposals
        self.pendingAction = pendingAction
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        intent = try c.decode(MealIntent.self, forKey: .intent)
        candidates = try c.decodeIfPresent([FoodCandidateDTO].self, forKey: .candidates) ?? []
        clarifyingQuestion = try c.decodeIfPresent(String.self, forKey: .clarifyingQuestion)
        correction = try c.decodeIfPresent(String.self, forKey: .correction)
        suggestedTemplateId = try c.decodeIfPresent(String.self, forKey: .suggestedTemplateId)
        assistantMessage = try c.decodeIfPresent(String.self, forKey: .assistantMessage) ?? ""
        warnings = try c.decodeIfPresent([String].self, forKey: .warnings) ?? []
        memoryProposals = try c.decodeIfPresent([MemoryProposalDTO].self, forKey: .memoryProposals)
        pendingAction = try c.decodeIfPresent(PendingActionDTO.self, forKey: .pendingAction)
        suggestionBudget = try c.decodeIfPresent(SuggestionBudgetDTO.self, forKey: .suggestionBudget)
        suggestionOptions = try c.decodeIfPresent([SuggestionOptionDTO].self, forKey: .suggestionOptions)
        workingMemory = try c.decodeIfPresent(WorkingMemoryPayload.self, forKey: .workingMemory)
        conversation = try c.decodeIfPresent(ConversationContextDTO.self, forKey: .conversation)
        messages = try c.decodeIfPresent([ThreadMessageDTO].self, forKey: .messages)
        pageInfo = try c.decodeIfPresent(ThreadPageInfoDTO.self, forKey: .pageInfo)
    }

    private enum CodingKeys: String, CodingKey {
        case intent, candidates, clarifyingQuestion, correction, suggestedTemplateId
        case assistantMessage, warnings, memoryProposals, pendingAction, suggestionBudget, suggestionOptions
        case workingMemory, conversation, messages, pageInfo
    }

    func workingMemoryPayload() -> WorkingMemoryPayload? {
        if let workingMemory { return workingMemory }
        if let pending = pendingAction {
            let cands = pending.payload.candidates.isEmpty ? candidates : pending.payload.candidates
            return WorkingMemoryPayload(
                pendingIntent: pending.type.rawValue,
                clarifyingQuestion: pending.prompt.isEmpty ? clarifyingQuestion : pending.prompt,
                candidates: cands.map {
                    WorkingMemoryCandidate(
                        foodId: $0.foodId,
                        displayName: $0.displayName,
                        grams: $0.grams,
                        source: $0.source
                    )
                },
                pendingAction: pending
            )
        }
        guard intent == .clarify || !candidates.isEmpty else { return nil }
        return WorkingMemoryPayload(
            pendingIntent: intent.rawValue,
            clarifyingQuestion: clarifyingQuestion,
            candidates: candidates.map {
                WorkingMemoryCandidate(
                    foodId: $0.foodId,
                    displayName: $0.displayName,
                    grams: $0.grams,
                    source: $0.source
                )
            },
            pendingAction: nil
        )
    }

    func structuredPayloadJSON() -> String? {
        guard let payload = workingMemoryPayload(),
              let data = try? JSONEncoder().encode(payload),
              let string = String(data: data, encoding: .utf8)
        else { return nil }
        return string
    }
}

struct FoodCandidateDTO: Codable, Equatable, Sendable {
    var foodId: String
    var displayName: String
    var grams: Double?
    var confidence: Double?
    var source: String?
    var provisionalPer100g: MacroTotals?
    var citationUrl: String?
}

struct MemoryProposalDTO: Codable, Equatable, Sendable {
    var action: MemoryProposalAction
    var id: String?
    var text: String?
}

struct HouseholdMeasureDTO: Codable, Equatable, Sendable {
    var id: String
    var label: String
    var grams: Double
}

struct ResolvedItemDTO: Codable, Equatable, Sendable {
    var foodId: String
    var displayName: String
    var grams: Double
    var per100g: MacroTotals
    var source: String
    var citationUrl: String?
    var portionLabel: String?
    var family: String?
    var measures: [HouseholdMeasureDTO]?
    var entryId: String?
    var itemIndex: Int?
}

struct ClarifyOptionDTO: Codable, Equatable, Sendable {
    var id: String
    var label: String
    var foodId: String?
    var grams: Double?
    var per100g: MacroTotals?
    var source: String?
    var family: String?
    var citationUrl: String?
    var measures: [HouseholdMeasureDTO]?
}

struct PendingActionPayloadDTO: Codable, Equatable, Sendable {
    var candidates: [FoodCandidateDTO]
    var memoryText: String?
    var suggestionOptions: [SuggestionOptionDTO]?
    var resolvedItems: [ResolvedItemDTO]
    var clarifyOptions: [ClarifyOptionDTO]
    var entryId: String?
    var dayKey: String?
    var itemIndex: Int?
    var correctionOp: String?
    var freeTextGrams: Bool
    var manualLog: Bool
    var reason: String?

    init(
        candidates: [FoodCandidateDTO] = [],
        memoryText: String? = nil,
        suggestionOptions: [SuggestionOptionDTO]? = nil,
        resolvedItems: [ResolvedItemDTO] = [],
        clarifyOptions: [ClarifyOptionDTO] = [],
        entryId: String? = nil,
        dayKey: String? = nil,
        itemIndex: Int? = nil,
        correctionOp: String? = nil,
        freeTextGrams: Bool = false,
        manualLog: Bool = false,
        reason: String? = nil
    ) {
        self.candidates = candidates
        self.memoryText = memoryText
        self.suggestionOptions = suggestionOptions
        self.resolvedItems = resolvedItems
        self.clarifyOptions = clarifyOptions
        self.entryId = entryId
        self.dayKey = dayKey
        self.itemIndex = itemIndex
        self.correctionOp = correctionOp
        self.freeTextGrams = freeTextGrams
        self.manualLog = manualLog
        self.reason = reason
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        candidates = try c.decodeIfPresent([FoodCandidateDTO].self, forKey: .candidates) ?? []
        memoryText = try c.decodeIfPresent(String.self, forKey: .memoryText)
        suggestionOptions = try c.decodeIfPresent([SuggestionOptionDTO].self, forKey: .suggestionOptions)
        resolvedItems = try c.decodeIfPresent([ResolvedItemDTO].self, forKey: .resolvedItems) ?? []
        clarifyOptions = try c.decodeIfPresent([ClarifyOptionDTO].self, forKey: .clarifyOptions) ?? []
        entryId = try c.decodeIfPresent(String.self, forKey: .entryId)
        dayKey = try c.decodeIfPresent(String.self, forKey: .dayKey)
        itemIndex = try c.decodeIfPresent(Int.self, forKey: .itemIndex)
        correctionOp = try c.decodeIfPresent(String.self, forKey: .correctionOp)
        freeTextGrams = try c.decodeIfPresent(Bool.self, forKey: .freeTextGrams) ?? false
        manualLog = try c.decodeIfPresent(Bool.self, forKey: .manualLog) ?? false
        reason = try c.decodeIfPresent(String.self, forKey: .reason)
    }

    private enum CodingKeys: String, CodingKey {
        case candidates, memoryText, suggestionOptions, resolvedItems, clarifyOptions
        case entryId, dayKey, itemIndex, correctionOp, freeTextGrams, manualLog, reason
    }
}

struct PendingActionDTO: Codable, Equatable, Sendable {
    var type: PendingActionType
    var prompt: String
    var payload: PendingActionPayloadDTO

    init(
        type: PendingActionType,
        prompt: String,
        payload: PendingActionPayloadDTO = PendingActionPayloadDTO()
    ) {
        self.type = type
        self.prompt = prompt
        self.payload = payload
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        type = try c.decode(PendingActionType.self, forKey: .type)
        prompt = try c.decodeIfPresent(String.self, forKey: .prompt) ?? ""
        payload = try c.decodeIfPresent(PendingActionPayloadDTO.self, forKey: .payload)
            ?? PendingActionPayloadDTO()
    }

    private enum CodingKeys: String, CodingKey {
        case type, prompt, payload
    }
}


struct SuggestionOptionItemDTO: Codable, Equatable, Sendable {
    var foodId: String
    var displayName: String
    var grams: Double?
    var source: String?
    var provisionalPer100g: MacroTotals?
    var per100g: MacroTotals?
    var citationUrl: String?
    var portionLabel: String?
    var family: String?
    var measures: [HouseholdMeasureDTO]?
}

struct SuggestionOptionDTO: Codable, Equatable, Sendable {
    var id: String
    var title: String
    var reason: String?
    var items: [SuggestionOptionItemDTO]
    var totals: MacroTotals?
    var fit: String?
    var overBy: [String: Double]?
}

struct SuggestionBudgetDTO: Codable, Equatable, Sendable {
    var calories: Double?
    var proteinG: Double?
    var carbsG: Double?
    var fatG: Double?

    var budget: SuggestionBudget? {
        guard let calories, calories > 0 else { return nil }
        return SuggestionBudget(calories: calories, proteinG: proteinG, carbsG: carbsG, fatG: fatG)
    }
}
