import Foundation

enum MealIntent: String, Codable, Equatable, Sendable {
    case logMeal = "log_meal"
    case suggestMeal = "suggest_meal"
    case correctMeal = "correct_meal"
    case clarify
    case updatePreference = "update_preference"
    case updateMemory = "update_memory"
    case unknown
}

struct PreferenceContextDTO: Codable, Equatable, Sendable {
    var likes: [String]
    var dislikes: [String]
    var allergies: [String]
    var diets: [String]
}

struct DiaryDaySummaryDTO: Codable, Equatable, Sendable {
    var dayKey: String
    var mealCount: Int
    var itemNames: [String]
}

struct DiaryEntryDTO: Codable, Equatable, Sendable {
    var name: String
    var mealSlot: String?
    var grams: Double?
}

struct DiaryContextDTO: Codable, Equatable, Sendable {
    var today: [DiaryEntryDTO]
    var previousDays: [DiaryDaySummaryDTO]
    var remaining: MacroTotals
    var remainingSource: String
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
    var summary: String
    var recentTurns: [ConversationTurnDTO]
    var workingMemory: WorkingMemoryPayload?
}

struct InterpretContextDTO: Codable, Equatable, Sendable {
    var assistanceLevel: String
    var lastIntent: String?
}

struct InterpretMealRequest: Codable, Equatable, Sendable {
    var utterance: String
    var timezone: String
    var dayKey: String
    var preferenceContext: PreferenceContextDTO
    var diaryContext: DiaryContextDTO
    var longTermMemory: [LongTermMemoryNoteDTO]
    var conversation: ConversationContextDTO
    var context: InterpretContextDTO

    /// Legacy alias fields for #37 memory snapshot contract coverage.
    var memorySnapshot: MemorySnapshotDTO?
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

struct FoodCandidateDTO: Codable, Equatable, Sendable {
    var foodId: String
    var displayName: String
    var grams: Double?
    var confidence: Double?
}

enum MemoryProposalAction: String, Codable, Equatable, Sendable {
    case add
    case update
    case delete
}

struct MemoryProposalDTO: Codable, Equatable, Sendable {
    var action: MemoryProposalAction
    var id: String?
    var text: String?
}

struct InterpretMealResponse: Codable, Equatable, Sendable {
    var intent: MealIntent
    var candidates: [FoodCandidateDTO]
    var clarifyingQuestion: String?
    var correction: String?
    var suggestedTemplateId: String?
    var assistantMessage: String
    var warnings: [String]
    var memoryProposals: [MemoryProposalDTO]?

    func workingMemoryPayload() -> WorkingMemoryPayload? {
        guard intent == .clarify || !candidates.isEmpty else { return nil }
        return WorkingMemoryPayload(
            pendingIntent: intent.rawValue,
            clarifyingQuestion: clarifyingQuestion,
            candidates: candidates.map {
                WorkingMemoryCandidate(foodId: $0.foodId, displayName: $0.displayName, grams: $0.grams)
            }
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
