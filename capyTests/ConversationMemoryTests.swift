import XCTest
import SwiftData
@testable import capy

final class ConversationMemoryTests: XCTestCase {
    private var container: ModelContainer!

    override func setUpWithError() throws {
        let schema = Schema([
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

    func testServerContextRequestOmitsConversation() throws {
        let request = InterpretMealRequestDTO.serverContext(
            utterance: "rice",
            dayKey: "2026-10-12",
            timezone: "America/Chicago"
        )
        XCTAssertTrue(request.useServerContext)
        XCTAssertEqual(request.utterance, "rice")
        XCTAssertEqual(request.dayKey, "2026-10-12")
        XCTAssertEqual(request.timezone, "America/Chicago")
        XCTAssertTrue(request.conversation.recentTurns.isEmpty)

        let data = try JSONEncoder().encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertEqual(json?["useServerContext"] as? Bool, true)
        XCTAssertNil(json?["conversation"])
        XCTAssertNil(json?["preferenceContext"])
        XCTAssertNil(json?["diaryContext"])
    }
}
