import Foundation
import SwiftData

enum ProfileSyncBuilder {
    static func patchPayload(modelContext: ModelContext) -> PatchProfilePayload {
        let prefs = (try? modelContext.fetch(FetchDescriptor<UserPreference>())) ?? []
        let mealTypes = (try? modelContext.fetch(
            FetchDescriptor<MealType>(sortBy: [SortDescriptor(\.sortOrder)])
        )) ?? []
        let targets = (try? modelContext.fetch(
            FetchDescriptor<DailyTarget>(sortBy: [SortDescriptor(\.effectiveDate, order: .reverse)])
        )) ?? []
        let settings = (try? modelContext.fetch(FetchDescriptor<AppSettings>()))?.first
        let target = targets.first

        let mealPlan = mealTypes
            .filter(\.isEnabled)
            .map { MealPlanSlotDTO(name: $0.name, sortOrder: $0.sortOrder, enabled: true) }

        let ltm = LongTermMemoryStore.notesForContext(in: modelContext).map {
            LongTermMemoryNoteDTO(id: $0.id, text: $0.text)
        }

        return PatchProfilePayload(
            timezone: TimeZone.current.identifier,
            dailyTarget: target.map {
                DailyTargetDTO(
                    calories: $0.calories,
                    proteinG: $0.proteinG,
                    carbsG: $0.carbsG,
                    fatG: $0.fatG
                )
            },
            mealPlan: mealPlan,
            likes: prefs.filter { $0.kind == .like }.map(\.value),
            dislikes: prefs.filter { $0.kind == .dislike }.map(\.value),
            allergies: prefs.filter { $0.kind == .allergy }.map(\.value),
            diets: prefs.filter { $0.kind == .diet }.map(\.value),
            assistanceLevel: settings?.assistanceLevel.rawValue ?? AssistanceLevel.fullAssist.rawValue,
            responseStyle: settings?.responseStyle.rawValue ?? ResponseStyle.balanced.rawValue,
            longTermMemory: ltm
        )
    }
}
