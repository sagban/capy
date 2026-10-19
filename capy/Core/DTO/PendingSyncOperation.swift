import Foundation

struct PendingSyncOperation: Codable, Identifiable, Equatable {
    var id: UUID
    var kind: PendingSyncKind
    var enqueuedAt: Date
    var logMeal: LogMealPayload?
    var deleteMeal: DeleteMealPayload?
    var patchProfile: PatchProfilePayload?

    static func logMeal(_ payload: LogMealPayload) -> PendingSyncOperation {
        PendingSyncOperation(
            id: UUID(),
            kind: .logMeal,
            enqueuedAt: .now,
            logMeal: payload,
            deleteMeal: nil,
            patchProfile: nil
        )
    }

    static func deleteMeal(_ payload: DeleteMealPayload) -> PendingSyncOperation {
        PendingSyncOperation(
            id: UUID(),
            kind: .deleteMeal,
            enqueuedAt: .now,
            logMeal: nil,
            deleteMeal: payload,
            patchProfile: nil
        )
    }

    static func patchProfile(_ payload: PatchProfilePayload) -> PendingSyncOperation {
        PendingSyncOperation(
            id: UUID(),
            kind: .patchProfile,
            enqueuedAt: .now,
            logMeal: nil,
            deleteMeal: nil,
            patchProfile: payload
        )
    }
}
