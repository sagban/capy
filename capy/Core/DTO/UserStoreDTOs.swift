import Foundation

// MARK: - log_meal

struct LogMealItemDTO: Codable, Equatable, Sendable {
    var name: String
    var grams: Double
    var foodId: String?
    var source: String?
    var per100g: MacroTotals?
    var ingredientFamily: String?
}

struct LogMealPayload: Codable, Equatable, Sendable {
    var clientMutationId: String
    var dayKey: String
    var mealSlot: String
    var entryId: String
    var confirmed: Bool
    var items: [LogMealItemDTO]
}

// MARK: - delete_meal

struct DeleteMealPayload: Codable, Equatable, Sendable {
    var clientMutationId: String
    var dayKey: String
    var entryId: String
}

// MARK: - patch_profile

struct DailyTargetDTO: Codable, Equatable, Sendable {
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
}

struct PatchProfilePayload: Codable, Equatable, Sendable {
    var timezone: String?
    var dailyTarget: DailyTargetDTO?
    var mealPlan: [MealPlanSlotDTO]?
    var likes: [String]?
    var dislikes: [String]?
    var allergies: [String]?
    var diets: [String]?
    var assistanceLevel: String?
    var responseStyle: String?
    var longTermMemory: [LongTermMemoryNoteDTO]?
}

// MARK: - library

struct UpsertLibraryItemPayload: Codable, Equatable, Sendable {
    var clientMutationId: String
    var item: LibraryItemSyncDTO
}

struct DeleteLibraryItemPayload: Codable, Equatable, Sendable {
    var clientMutationId: String
    var id: String
}

struct LibraryItemSyncDTO: Codable, Equatable, Sendable {
    var id: String
    var name: String
    var kind: String
    var origin: String
    var detail: String
    var calories: Double
    var proteinG: Double
    var carbsG: Double
    var fatG: Double
    var servingGrams: Double
    var sourceFoodId: String
    var ingredients: [LibraryIngredientLine]
    var createdAt: String?
    var updatedAt: String?
    var deleted: Bool?
}

struct ListLibraryResponseDTO: Codable, Equatable, Sendable {
    var items: [LibraryItemSyncDTO]
}
