import Foundation
import SwiftData

/// Shared diary write path for Capy confirm and Manual Log.
enum MealCommit {
    struct LogNewResult: Equatable {
        var added: MacroTotals
        var names: [String]
    }

    /// One Food Log row per food (not one multi-item meal card).
    @discardableResult
    static func logNewEntries(
        lines: [MealCommitLine],
        dayKey: String,
        mealSlot: String?,
        upsertAILibrary: Bool,
        in context: ModelContext
    ) -> LogNewResult {
        var added = MacroTotals.zero
        var names: [String] = []
        let slot = mealSlot.flatMap { $0.isEmpty ? nil : $0 }
        for line in lines {
            let macros = line.macros
            let item = MealEntryItem(
                name: line.name,
                grams: line.grams,
                calories: macros.calories,
                proteinG: macros.proteinG,
                carbsG: macros.carbsG,
                fatG: macros.fatG,
                foodId: line.foodId,
                ingredientFamily: line.family,
                source: line.source
            )
            let entry = MealEntry(
                dayKey: dayKey,
                mealSlot: slot,
                originalUserText: ReadableFoodName.display(line.name),
                confirmed: true,
                items: []
            )
            context.insert(entry)
            item.entry = entry
            entry.items.append(item)
            if upsertAILibrary, let per100g = line.per100g {
                LibraryItem.upsertFromAcceptedAgentLine(
                    name: line.name,
                    foodId: line.foodId,
                    grams: line.grams,
                    per100g: per100g,
                    source: line.source,
                    citationUrl: line.citationUrl,
                    portionLabel: line.portionLabel,
                    in: context
                )
            }
            sync(entry, in: context)
            added = added + macros
            names.append(ReadableFoodName.display(line.name))
        }
        return LogNewResult(added: added, names: names)
    }

    /// Replace or create a single manual-log entry (one item).
    @discardableResult
    static func saveManualEntry(
        line: MealCommitLine,
        dayKey: String,
        mealSlot: String?,
        existing: MealEntry?,
        barcodePerServing: MacroTotals?,
        barcodeDetail: String,
        in context: ModelContext
    ) -> MealEntry {
        let macros = line.macros
        let item = MealEntryItem(
            name: line.name,
            grams: line.grams,
            calories: macros.calories,
            proteinG: macros.proteinG,
            carbsG: macros.carbsG,
            fatG: macros.fatG,
            foodId: line.foodId,
            ingredientFamily: line.family,
            source: line.source
        )
        let entry: MealEntry
        if let existing {
            for old in existing.items {
                context.delete(old)
            }
            existing.dayKey = dayKey
            existing.mealSlot = mealSlot
            existing.originalUserText = line.name
            existing.confirmed = true
            item.entry = existing
            existing.items = [item]
            entry = existing
        } else {
            let created = MealEntry(
                dayKey: dayKey,
                mealSlot: mealSlot,
                originalUserText: line.name,
                confirmed: true,
                items: []
            )
            item.entry = created
            created.items = [item]
            context.insert(created)
            entry = created
        }
        if line.foodId.hasPrefix("off_"), let perServing = barcodePerServing {
            LibraryItem.updateFromBarcodeLog(
                foodId: line.foodId,
                name: line.name,
                detail: barcodeDetail,
                perServing: perServing,
                in: context
            )
        }
        sync(entry, in: context)
        return entry
    }

    static func applyCorrection(
        line: MealCommitLine,
        to entry: MealEntry,
        in context: ModelContext
    ) -> MacroTotals? {
        let index = line.itemIndex ?? 0
        guard entry.items.indices.contains(index) else { return nil }
        let item = entry.items[index]
        let macros = line.macros
        item.name = line.name
        item.grams = line.grams
        item.calories = macros.calories
        item.proteinG = macros.proteinG
        item.carbsG = macros.carbsG
        item.fatG = macros.fatG
        item.foodId = line.foodId
        item.ingredientFamily = line.family
        item.source = line.source
        sync(entry, in: context)
        return macros
    }

    static func removeItem(
        entry: MealEntry,
        itemIndex: Int,
        in context: ModelContext
    ) {
        if entry.items.indices.contains(itemIndex) {
            let item = entry.items[itemIndex]
            entry.items.remove(at: itemIndex)
            context.delete(item)
        }
        if entry.items.isEmpty {
            context.delete(entry)
            try? context.save()
        } else {
            sync(entry, in: context)
        }
    }

    static func deleteEntry(
        _ entry: MealEntry,
        entryId: String,
        dayKey: String,
        in context: ModelContext
    ) {
        for item in entry.items {
            context.delete(item)
        }
        context.delete(entry)
        try? context.save()
        UserSyncService.shared.enqueueDeleteMeal(entryId: entryId, dayKey: dayKey)
    }

    static func sync(_ entry: MealEntry, in context: ModelContext) {
        try? context.save()
        UserSyncService.shared.enqueueLogMeal(entry)
    }

    static func loggedReply(
        names: [String],
        added: MacroTotals,
        eatenBefore: MacroTotals,
        target: MacroTotals,
        assistance: AssistanceLevel
    ) -> String {
        guard !names.isEmpty else { return "logged." }
        let left = MacroTotals.remaining(target: target, eaten: eatenBefore + added)
        let listed = listedNames(names)
        if assistance == .quiet {
            return "logged \(listed). \(Int(left.calories)) left."
        }
        return "logged \(listed). \(Int(added.calories)) cal. \(Int(left.calories)) cal left."
    }

    static func listedNames(_ names: [String]) -> String {
        if names.count <= 1 { return names.first ?? "that" }
        if names.count == 2 { return "\(names[0]) and \(names[1])" }
        return names.dropLast().joined(separator: ", ") + ", and " + (names.last ?? "")
    }
}
