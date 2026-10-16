import XCTest
import SwiftData
@testable import capy

final class ConversationMemoryTests: XCTestCase {
    private var container: ModelContainer!

    override func setUpWithError() throws {
        let schema = Schema([
            ConversationThread.self,
            ConversationTurn.self,
            LongTermMemoryNote.self,
            UserPreference.self,
            MealEntry.self,
            MealEntryItem.self,
            DailyTarget.self,
            AppSettings.self,
            MealTemplate.self,
            MealTemplateItem.self,
            Food.self,
        ])
        let config = ModelConfiguration(isStoredInMemoryOnly: true)
        container = try ModelContainer(for: schema, configurations: [config])
    }

    func testTrimFoldsIntoSummary() throws {
        let context = ModelContext(container)
        for i in 0..<15 {
            ConversationMemoryStore.appendTurn(
                role: i % 2 == 0 ? .user : .assistant,
                text: "turn \(i)",
                in: context
            )
        }
        let thread = ConversationMemoryStore.thread(in: context)
        XCTAssertLessThanOrEqual(ConversationMemoryStore.orderedTurns(thread).count, ConversationMemoryStore.windowSize)
        XCTAssertFalse(thread.summary.isEmpty)
    }

    func testWorkingMemorySurvivesClarify() throws {
        let context = ModelContext(container)
        let payload = WorkingMemoryPayload(
            pendingIntent: "clarify",
            clarifyingQuestion: "cup or half?",
            candidates: [
                WorkingMemoryCandidate(foodId: "usda_168878", displayName: "Rice", grams: nil)
            ]
        )
        let data = try JSONEncoder().encode(payload)
        let json = String(data: data, encoding: .utf8)
        ConversationMemoryStore.appendTurn(role: .user, text: "some rice", in: context)
        ConversationMemoryStore.appendTurn(
            role: .assistant,
            text: "quick check",
            structuredPayload: json,
            in: context
        )
        let thread = ConversationMemoryStore.thread(in: context)
        let wm = ConversationMemoryStore.workingMemory(from: thread)
        XCTAssertEqual(wm?.pendingIntent, "clarify")
        XCTAssertEqual(wm?.candidates.first?.foodId, "usda_168878")
    }

    func testLongTermMemoryProposalsAndDayRollover() throws {
        let context = ModelContext(container)
        LongTermMemoryStore.apply(
            proposals: [
                MemoryProposalDTO(action: .add, id: "mem_1", text: "No microwave at work")
            ],
            in: context
        )
        XCTAssertEqual(LongTermMemoryStore.allNotes(in: context).count, 1)
        ConversationMemoryStore.noteDayRollover(previousDayKey: "2026-10-11", mealCount: 2, in: context)
        let thread = ConversationMemoryStore.thread(in: context)
        XCTAssertTrue(thread.summary.contains("2026-10-11"))
        XCTAssertEqual(LongTermMemoryStore.allNotes(in: context).count, 1)

        LongTermMemoryStore.apply(
            proposals: [MemoryProposalDTO(action: .delete, id: "mem_1", text: nil)],
            in: context
        )
        XCTAssertTrue(LongTermMemoryStore.allNotes(in: context).isEmpty)
    }

    func testMemoryNotesDoNotWriteDietPrefs() throws {
        let context = ModelContext(container)
        LongTermMemoryStore.apply(
            proposals: [MemoryProposalDTO(action: .add, text: "I am vegetarian")],
            in: context
        )
        let prefs = (try? context.fetch(FetchDescriptor<UserPreference>())) ?? []
        XCTAssertTrue(prefs.isEmpty)
        XCTAssertEqual(LongTermMemoryStore.allNotes(in: context).first?.text, "I am vegetarian")
    }

    func testContextBuilderPacksLayers() throws {
        let context = ModelContext(container)
        context.insert(UserPreference(kind: .diet, value: "vegetarian"))
        context.insert(DailyTarget(calories: 2000, proteinG: 140, carbsG: 200, fatG: 65))
        LongTermMemoryStore.add(text: "Trains Tuesdays", source: .user, in: context)
        ConversationMemoryStore.appendTurn(role: .user, text: "hi", in: context)
        let request = ContextBuilder.buildInterpretRequest(
            utterance: "rice",
            dayKey: "2026-10-12",
            timezone: "America/Chicago",
            modelContext: context
        )
        XCTAssertEqual(request.preferenceContext.diets, ["vegetarian"])
        XCTAssertEqual(request.diaryContext.remainingSource, "clientComputed")
        XCTAssertEqual(request.longTermMemory.first?.text, "Trains Tuesdays")
        XCTAssertEqual(request.conversation.recentTurns.count, 1)
        XCTAssertEqual(request.conversation.threadId, "default")
        XCTAssertNotNil(request.memorySnapshot)
    }
}
