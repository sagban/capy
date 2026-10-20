import Foundation
import SwiftData

/// Applies Capy HITL confirm / correction / delete to SwiftData via `MealCommit`.
enum CapyConfirmApplier {
    struct Outcome: Equatable {
        var reply: String
    }

    static func applyConfirm(
        lines: [ConfirmLine],
        correctionOp: String?,
        mealSlot: String,
        dayKey: String,
        entries: [MealEntry],
        target: MacroTotals,
        eaten: MacroTotals,
        assistance: AssistanceLevel,
        in context: ModelContext
    ) -> Outcome? {
        if correctionOp == "remove", let line = lines.first, let entryId = line.entryId {
            if let entry = entries.first(where: { $0.uuid.uuidString == entryId }) {
                MealCommit.removeItem(entry: entry, itemIndex: line.itemIndex ?? 0, in: context)
            }
            return Outcome(reply: "removed.")
        }

        if let line = lines.first, let entryId = line.entryId,
           let entry = entries.first(where: { $0.uuid.uuidString == entryId }) {
            guard let macros = MealCommit.applyCorrection(line: line.commitLine, to: entry, in: context) else {
                return nil
            }
            let left = MacroTotals.remaining(target: target, eaten: eaten)
            return Outcome(reply: "updated — \(Int(macros.calories)) cal. \(Int(left.calories)) cal left.")
        }

        let result = MealCommit.logNewEntries(
            lines: lines.map(\.commitLine),
            dayKey: dayKey,
            mealSlot: mealSlot,
            upsertAILibrary: true,
            in: context
        )
        guard !result.names.isEmpty else { return nil }
        let reply = MealCommit.loggedReply(
            names: result.names,
            added: result.added,
            eatenBefore: eaten,
            target: target,
            assistance: assistance
        )
        return Outcome(reply: reply)
    }

    static func applyDelete(
        pending: PendingDeleteContext,
        entries: [MealEntry],
        in context: ModelContext
    ) -> Outcome {
        if let entry = entries.first(where: { $0.uuid.uuidString == pending.entryId }) {
            MealCommit.deleteEntry(
                entry,
                entryId: pending.entryId,
                dayKey: pending.dayKey,
                in: context
            )
        } else {
            UserSyncService.shared.enqueueDeleteMeal(entryId: pending.entryId, dayKey: pending.dayKey)
        }
        let listed = ReadableFoodName.display(pending.label)
        return Outcome(reply: "deleted \(listed).")
    }
}
