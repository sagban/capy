import Foundation
import SwiftData

enum ContextBuilder {
    static func buildInterpretRequest(
        utterance: String,
        dayKey: String,
        timezone: String = TimeZone.current.identifier,
        modelContext: ModelContext
    ) -> InterpretMealRequest {
        let prefs = (try? modelContext.fetch(FetchDescriptor<UserPreference>())) ?? []
        let preferenceContext = PreferenceContextDTO(
            likes: prefs.filter { $0.kind == .like }.map(\.value),
            dislikes: prefs.filter { $0.kind == .dislike }.map(\.value),
            allergies: prefs.filter { $0.kind == .allergy }.map(\.value),
            diets: prefs.filter { $0.kind == .diet }.map(\.value)
        )

        let entries = (try? modelContext.fetch(FetchDescriptor<MealEntry>())) ?? []
        let todayEntries = entries.filter { $0.dayKey == dayKey && $0.confirmed }
        let todayDTO: [DiaryEntryDTO] = todayEntries.flatMap { entry in
            entry.items.map {
                DiaryEntryDTO(name: $0.name, mealSlot: entry.mealSlot, grams: $0.grams)
            }
        }

        let previousKeys = previousDayKeys(from: dayKey, count: 7)
        let previousDays: [DiaryDaySummaryDTO] = previousKeys.compactMap { key in
            let dayEntries = entries.filter { $0.dayKey == key && $0.confirmed }
            guard !dayEntries.isEmpty else { return nil }
            let names = dayEntries.flatMap { $0.items.map(\.name) }
            return DiaryDaySummaryDTO(dayKey: key, mealCount: dayEntries.count, itemNames: names)
        }

        let targets = (try? modelContext.fetch(
            FetchDescriptor<DailyTarget>(sortBy: [SortDescriptor(\.effectiveDate, order: .reverse)])
        )) ?? []
        let targetModel = targets.first
        let target = MacroTotals(
            calories: targetModel?.calories ?? 2000,
            proteinG: targetModel?.proteinG ?? 140,
            carbsG: targetModel?.carbsG ?? 200,
            fatG: targetModel?.fatG ?? 65
        )
        let eaten = todayEntries.reduce(MacroTotals.zero) { partial, entry in
            partial + MacroTotals(
                calories: entry.calories,
                proteinG: entry.proteinG,
                carbsG: entry.carbsG,
                fatG: entry.fatG
            )
        }
        let remaining = MacroTotals.remaining(target: target, eaten: eaten)

        let diaryContext = DiaryContextDTO(
            today: todayDTO,
            previousDays: previousDays,
            remaining: remaining,
            remainingSource: "clientComputed"
        )

        let ltm = LongTermMemoryStore.notesForContext(in: modelContext).map {
            LongTermMemoryNoteDTO(id: $0.id, text: $0.text)
        }

        let thread = ConversationMemoryStore.thread(in: modelContext)
        let recent = ConversationMemoryStore.recentTurns(thread).map {
            ConversationTurnDTO(role: $0.role.rawValue, text: $0.text)
        }
        let conversation = ConversationContextDTO(
            summary: thread.summary,
            recentTurns: recent,
            workingMemory: ConversationMemoryStore.workingMemory(from: thread)
        )

        let settings = (try? modelContext.fetch(FetchDescriptor<AppSettings>()))?.first
        let level = settings?.assistanceLevel.rawValue ?? AssistanceLevel.fullAssist.rawValue
        let lastIntent = conversation.workingMemory?.pendingIntent

        let templates = (try? modelContext.fetch(FetchDescriptor<MealTemplate>())) ?? []
        let memorySnapshot = MemorySnapshotDTO(
            preferences: preferenceContext.likes,
            dislikes: preferenceContext.dislikes,
            allergies: preferenceContext.allergies,
            diets: preferenceContext.diets,
            regularTemplateIds: templates.map(\.id),
            recentCorrections: []
        )

        return InterpretMealRequest(
            utterance: utterance,
            timezone: timezone,
            dayKey: dayKey,
            preferenceContext: preferenceContext,
            diaryContext: diaryContext,
            longTermMemory: ltm,
            conversation: conversation,
            context: InterpretContextDTO(assistanceLevel: level, lastIntent: lastIntent),
            memorySnapshot: memorySnapshot
        )
    }

    private static func previousDayKeys(from dayKey: String, count: Int) -> [String] {
        guard let date = DayKey.date(from: dayKey) else { return [] }
        let calendar = Calendar.current
        return (1...count).compactMap { offset in
            guard let d = calendar.date(byAdding: .day, value: -offset, to: date) else { return nil }
            return DayKey.make(from: d, calendar: calendar)
        }
    }
}
