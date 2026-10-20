import Foundation
import SwiftData

extension InterpretMealRequestDTO {
    /// Minimal `interpret_meal` body when the server loads profile, diary, and thread from Firestore.
    /// Still attaches a compact local library snapshot for strict title resolve.
    static func serverContext(
        utterance: String,
        dayKey: String,
        timezone: String = TimeZone.current.identifier,
        threadId: String = CapyThreadService.defaultThreadId,
        libraryContext: [LibraryItemRefDTO] = []
    ) -> InterpretMealRequestDTO {
        InterpretMealRequestDTO(
            utterance: utterance,
            timezone: timezone,
            dayKey: dayKey,
            libraryContext: libraryContext,
            threadId: threadId,
            useServerContext: true
        )
    }

    static func librarySnapshot(from items: [LibraryItem], limit: Int = 40) -> [LibraryItemRefDTO] {
        items.prefix(limit).map { item in
            LibraryItemRefDTO(
                id: item.uuidString,
                name: item.name,
                kind: item.kind.rawValue,
                calories: item.calories,
                proteinG: item.proteinG,
                carbsG: item.carbsG,
                fatG: item.fatG,
                servingGrams: item.agentServingGrams
            )
        }
    }
}

extension LibraryItem {
    /// Grams represented by the stored per-serving macros (composition sum, then stored serving).
    var agentServingGrams: Double {
        let fromParts = ingredients
            .filter { $0.source == .catalogFood || $0.servingGrams > 0 }
            .map(\.grams)
            .reduce(0, +)
        if fromParts > 0 { return fromParts }
        return max(servingGrams, 1)
    }
}
