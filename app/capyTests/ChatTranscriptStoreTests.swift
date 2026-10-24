import XCTest
import SwiftData
@testable import capy

@MainActor
final class ChatTranscriptStoreTests: XCTestCase {
    func testLatestKeepsNewestAndPendingStaysAtTheEnd() throws {
        let context = try makeContext()
        ChatTranscriptStore.upsert(
            messages: [
                ThreadMessageDTO(messageId: "a", role: "user", text: "eggs", createdAt: "2026-10-23T12:00:00Z", seq: 1),
                ThreadMessageDTO(messageId: "b", role: "assistant", text: "logged", createdAt: "2026-10-23T12:00:01Z", seq: 2),
                ThreadMessageDTO(messageId: "c", role: "user", text: "rice", createdAt: "2026-10-23T12:00:02Z", seq: 3),
            ],
            threadId: "default",
            in: context
        )
        ChatTranscriptStore.upsert(ChatBubble(serverMessageId: "local", role: .user, text: "offline oats"), threadId: "default", in: context)

        let page = ChatTranscriptStore.latest(threadId: "default", limit: 2, in: context)
        XCTAssertEqual(page.bubbles.map(\.text), ["rice", "offline oats"])
        XCTAssertTrue(page.hasMore)

        let older = ChatTranscriptStore.older(before: page.bubbles[0].id, threadId: "default", limit: 12, in: context)
        XCTAssertEqual(older.bubbles.map(\.text), ["eggs", "logged"])
        XCTAssertFalse(older.hasMore)
    }

    func testServerCopyReplacesThePhoneOnlyDuplicate() throws {
        let context = try makeContext()
        ChatTranscriptStore.upsert(ChatBubble(serverMessageId: "local", role: .user, text: "eggs"), threadId: "default", in: context)
        let page = [
            ThreadMessageDTO(messageId: "server", role: "user", text: "eggs", createdAt: "2026-10-23T12:00:00Z", seq: 4),
        ]
        ChatTranscriptStore.upsert(messages: page, threadId: "default", in: context)
        ChatTranscriptStore.absorbOptimisticDuplicates(matching: page, threadId: "default", in: context)

        let latest = ChatTranscriptStore.latest(threadId: "default", limit: 12, in: context)
        XCTAssertEqual(latest.bubbles.map(\.id), ["server"])
        XCTAssertTrue(ChatTranscriptStore.pending(threadId: "default", in: context).isEmpty)
    }

    func testClearDropsTheThread() throws {
        let context = try makeContext()
        ChatTranscriptStore.upsert(ChatBubble(role: .capy, text: "logged"), threadId: "default", in: context)
        ChatTranscriptStore.clear(threadId: "default", in: context)
        XCTAssertTrue(ChatTranscriptStore.latest(threadId: "default", limit: 12, in: context).bubbles.isEmpty)
    }

    func testAccountsDoNotShareATranscript() throws {
        let context = try makeContext()
        let first = ChatTranscriptStore.storageKey(uid: "user-a")
        let second = ChatTranscriptStore.storageKey(uid: "user-b")
        ChatTranscriptStore.upsert(ChatBubble(role: .user, text: "old account"), threadId: first, in: context)
        ChatTranscriptStore.upsert(ChatBubble(role: .user, text: "unscoped"), threadId: "default", in: context)
        ChatTranscriptStore.discardLegacyUnscoped(in: context)

        XCTAssertEqual(ChatTranscriptStore.all(threadId: first, in: context).map(\.text), ["old account"])
        XCTAssertTrue(ChatTranscriptStore.all(threadId: second, in: context).isEmpty)
        XCTAssertTrue(ChatTranscriptStore.all(threadId: "default", in: context).isEmpty)
    }

    private func makeContext() throws -> ModelContext {
        let container = try ModelContainer(
            for: Schema([ChatMessageRecord.self]),
            configurations: ModelConfiguration(isStoredInMemoryOnly: true)
        )
        return ModelContext(container)
    }
}
