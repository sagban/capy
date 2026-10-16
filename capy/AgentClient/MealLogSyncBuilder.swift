import Foundation

enum MealLogSyncBuilder {
    static func payload(for entry: MealEntry, clientMutationId: String) -> LogMealPayload? {
        let slot = (entry.mealSlot ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !slot.isEmpty, entry.confirmed else { return nil }

        let items: [LogMealItemDTO] = entry.items.compactMap { item in
            guard item.grams > 0 else { return nil }
            return LogMealItemDTO(
                name: item.name,
                grams: item.grams,
                foodId: item.foodId.isEmpty ? nil : item.foodId,
                source: item.source.isEmpty ? nil : item.source,
                per100g: item.per100gMacros,
                ingredientFamily: item.ingredientFamily.isEmpty ? nil : item.ingredientFamily
            )
        }
        guard !items.isEmpty else { return nil }

        return LogMealPayload(
            clientMutationId: clientMutationId,
            dayKey: entry.dayKey,
            mealSlot: slot,
            entryId: entry.uuid.uuidString,
            confirmed: true,
            items: items
        )
    }
}
